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

Response (via Lambda base run()):
    {"success": True, "data": [...]}
"""

from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, model_validator

from ..lambda_standalone.base import Lambda


class _ModelQuerySchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

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


class ModelQueryLambda(Lambda):
    """
    Base class for cross-service MongoDB query Lambdas.

    Subclass and override `allowed_collections` to declare which collections
    this Lambda exposes. Everything else is handled automatically.
    """

    @property
    def allowed_collections(self) -> List[str]:
        """
        Whitelist of collection names this Lambda is allowed to query.

        Must be overridden — an empty list rejects all requests.

        Example:
            @property
            def allowed_collections(self):
                return ["dockets", "tax_sales"]
        """
        return []

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

            cursor = collection.find(mongo_filter, fields or {})

            if skip:
                cursor = cursor.skip(skip)
            if limit:
                cursor = cursor.limit(limit)

            results = await cursor.to_list(length=None)

        return results
