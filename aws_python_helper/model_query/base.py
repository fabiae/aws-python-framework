"""
ModelQueryLambda - Generic MongoDB query proxy Lambda for inter-service communication.

Allows other microservices to query any whitelisted collection in this service's
MongoDB database by invoking this Lambda directly, passing standard MongoDB
query parameters (filter, pipeline, fields, limit, skip).

Usage — subclass and declare which collections are exposed:

    from aws_python_helper import ModelQueryLambda

    class DocketsModelQueryLambda(ModelQueryLambda):
        @property
        def allowed_collections(self) -> list:
            return ["dockets", "tax_sales"]

Caller payload:
    {
        "session": {"state": "connecticut"},
        "collection": "dockets",
        "filter":   {"case_type_code": "M10"},   # simple find — option A
        "pipeline": [...],                        # aggregate — option B (takes precedence)
        "fields":   {"docket_id": 1, "_id": 0},  # projection (only with filter)
        "limit":    100,                          # optional
        "skip":     0                             # optional, default 0
    }

ObjectId coercion:
    String values for '_id' (or 'id' as alias) inside `filter` and pipeline
    `$match` stages are automatically converted to bson.ObjectId. Supports
    scalar operators ($eq, $ne, $gt, $gte, $lt, $lte) and list operators
    ($in, $nin). A clear ValueError is raised when the string is not a valid
    24-char ObjectId hex.

    {"filter": {"_id": "65f1a2b3c4d5e6f7a8b9c0d1"}}
    {"filter": {"_id": {"$in": ["65f1...", "65f2..."]}}}
    {"filter": {"id":  "65f1a2b3c4d5e6f7a8b9c0d1"}}  # 'id' is aliased to '_id'

Response (via Lambda base run()):
    {"success": True, "data": [...]}
"""

from typing import Any, Dict, List, Optional, Union
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, model_validator

from ..lambda_standalone.base import Lambda


_OBJECT_ID_SCALAR_OPERATORS = {"$eq", "$ne", "$gt", "$gte", "$lt", "$lte"}
_OBJECT_ID_LIST_OPERATORS = {"$in", "$nin"}


def _coerce_object_id(value: Any) -> Any:
    """Convert a string (or operator dict) to ObjectId where applicable for an '_id' field."""
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str):
        if not ObjectId.is_valid(value):
            raise ValueError(f"'_id' value '{value}' is not a valid ObjectId")
        return ObjectId(value)
    if isinstance(value, dict):
        coerced = {}
        for op, op_value in value.items():
            if op in _OBJECT_ID_LIST_OPERATORS:
                if not isinstance(op_value, list):
                    raise ValueError(f"'{op}' value for '_id' must be a list")
                coerced[op] = [_coerce_object_id(v) for v in op_value]
            elif op in _OBJECT_ID_SCALAR_OPERATORS:
                coerced[op] = _coerce_object_id(op_value)
            else:
                coerced[op] = op_value
        return coerced
    raise ValueError(
        f"Unsupported type for '_id' filter: {type(value).__name__}"
    )


def _normalize_id_key(d: dict) -> None:
    """Rename 'id' → '_id' (if no _id present) and coerce its value to ObjectId in-place."""
    if "id" in d and "_id" not in d:
        d["_id"] = d.pop("id")
    if "_id" in d:
        d["_id"] = _coerce_object_id(d["_id"])


class _ModelQuerySchema(BaseModel):
    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    collection: str
    filter: Optional[dict] = None
    pipeline: Optional[list] = None
    fields: Optional[dict] = None
    limit: Optional[int] = None
    skip: int = 0

    @model_validator(mode="after")
    def _pipeline_fields_exclusive(self):
        if self.pipeline is not None and self.fields is not None:
            raise ValueError("'fields' cannot be used together with 'pipeline'")
        return self

    @model_validator(mode="after")
    def _normalize_object_ids(self):
        if self.filter is not None:
            _normalize_id_key(self.filter)
        if self.pipeline is not None:
            for stage in self.pipeline:
                if isinstance(stage, dict) and isinstance(stage.get("$match"), dict):
                    _normalize_id_key(stage["$match"])
        return self


def _enforce_exclusions(
    fields: Optional[dict], excluded: List[str]
) -> dict:
    """The projection the owner allows, whatever the caller asked for.

    Mongo reads a projection as inclusive or exclusive, never both, so the
    forbidden fields are dropped from an inclusive one and added to an exclusive
    one. `_id` is ignored when deciding which it is: it may appear in either.
    """
    projection = dict(fields or {})
    if not excluded:
        return projection

    inclusive = any(value for key, value in projection.items() if key != "_id")
    if not inclusive:
        for name in excluded:
            projection[name] = 0
        return projection

    for name in excluded:
        projection.pop(name, None)

    # Pedir sólo el campo prohibido dejaría la proyección vacía, y una
    # proyección vacía en Mongo devuelve el documento entero: exactamente lo
    # contrario de lo buscado. Sin nada legítimo que pedir, sólo el id.
    if not any(value for key, value in projection.items() if key != "_id"):
        return {"_id": 1}
    return projection


class ModelQueryLambda(Lambda):
    """
    Base class for cross-service MongoDB query Lambdas.

    Subclass and override `allowed_collections` to declare which collections
    this Lambda exposes. Everything else is handled automatically.
    """

    @property
    def allowed_collections(self) -> Union[List[str], Dict[str, dict]]:
        """
        Whitelist of collection names this Lambda is allowed to query.

        Must be overridden — an empty list rejects all requests.

        A list exposes each collection whole:

            @property
            def allowed_collections(self):
                return ["dockets", "tax_sales"]

        A dict lets the owner keep fields in, whatever the caller projects. This
        is not `fields`: that one is the caller saying what it wants, this one is
        the owner saying what never leaves.

            @property
            def allowed_collections(self):
                return {"dockets": {}, "users": {"exclude": ["password"]}}
        """
        return []

    def excluded_fields(self, collection: str) -> List[str]:
        """Fields this collection never returns. Empty for list-style whitelists."""
        allowed = self.allowed_collections
        if not isinstance(allowed, dict):
            return []
        return list((allowed.get(collection) or {}).get("exclude") or [])

    @property
    def schema(self):
        return _ModelQuerySchema

    async def validate(self):
        collection = self.data.get("collection", "")

        if not self.allowed_collections:
            raise ValueError(
                "allowed_collections is not configured on this ModelQueryLambda"
            )

        if collection not in self.allowed_collections:
            allowed = ", ".join(self.allowed_collections)
            raise ValueError(
                f"Collection '{collection}' is not allowed. Allowed: {allowed}"
            )

        # Una pipeline puede renombrar un campo antes de que lo quitemos
        # ($addFields, $replaceRoot, $lookup), así que no hay forma honesta de
        # garantizar la exclusión sobre ella. Un $unset final daría una falsa
        # sensación de seguridad, que es peor que no tener la función.
        if self.excluded_fields(collection) and self.data.get("pipeline") is not None:
            raise ValueError(
                f"Collection '{collection}' hides fields, so it cannot be queried "
                f"with a pipeline. Use 'filter' instead."
            )

    async def process(self) -> Any:
        collection_name: str = self.data["collection"]
        database: str = self.data.get("database") or self.session.state

        collection = getattr(getattr(self.db, database), collection_name)

        pipeline: Optional[list] = self.data.get("pipeline")

        if pipeline is not None:
            results = await collection.aggregate(pipeline).to_list(length=None)
        else:
            mongo_filter: dict = self.data.get("filter") or {}
            fields: Optional[dict] = self.data.get("fields")
            limit: int = self.data.get("limit") or 0
            skip: int = self.data.get("skip") or 0

            projection = _enforce_exclusions(
                fields, self.excluded_fields(collection_name)
            )
            cursor = collection.find(mongo_filter, projection)

            if skip:
                cursor = cursor.skip(skip)
            if limit:
                cursor = cursor.limit(limit)

            results = await cursor.to_list(length=None)

        return results
