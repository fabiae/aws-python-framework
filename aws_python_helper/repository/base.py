"""
Repository Base - Base class for all MongoDB repository classes.

Eliminates boilerplate by providing automatic connection management,
collection access, and index creation without requiring the user to
pass a database connection or call any initialization method.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from ..database.mongo_manager import MongoManager
from ..database.external_mongo_manager import ExternalMongoManager
from ..context.session import get_session
from .audit import DEFAULT_STATUSES, STATUS, AuditedCollection


class Repository(ABC):
    """
    Base class for all MongoDB repositories.

    Subclasses only need to declare which collection they use,
    whether it is external, and what indexes to create.
    The connection, database resolution, and index creation are handled automatically.

    Required properties to override:
        collection_name (str): Name of the MongoDB collection.

    Optional properties to override:
        database_key (str | None): Explicit database name to use.
            - If set (e.g., 'core', 'smart_data'): always uses that database.
            - If None (default): uses session.state automatically.
              This makes the repository "state-scoped" — it connects to the database
              matching the current request state (e.g., 'connecticut', 'new_jersey').
        is_external (bool): Whether to use an external MongoDB cluster. Default: False.
        cluster_name (str): External cluster name. Required if is_external=True.
        indexes (list): List of index definitions to create automatically.
        audit (bool): Stamp created_at/created_by/updated_at/updated_by on every
            write. Default: True — no repository has to remember to do it.
        statuses (list[str] | None): Allowed values of the record's `status`.
            Default: ['active', 'inactive']. None means this collection has no
            status at all.
        default_status (str): What a new record gets. Default: the first of
            `statuses`.

    Usage:
        # Core repository — always uses 'core' database
        class TownsRepository(Repository):

            @property
            def collection_name(self):
                return "towns"

            @property
            def database_key(self):
                return "core"

            @property
            def indexes(self):
                return [
                    {"key": [("name", 1)]},
                    {"key": [("platform", 1)]},
                ]

            async def get_all(self):
                return await self.collection.find({}).to_list(length=None)

        # State-scoped repository — connects to the current session state database
        class LandRecordsRepository(Repository):

            @property
            def collection_name(self):
                return "land_records"
            # No database_key → uses session.state automatically

        # External cluster repository
        class AddressRepository(Repository):

            @property
            def database_key(self):
                return "smart_data"

            @property
            def collection_name(self):
                return "address"

            @property
            def is_external(self):
                return True

            @property
            def cluster_name(self):
                return "ClusterDockets"

        # Instantiate without passing any db connection
        repo = TownsRepository()
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._collection_cache: Dict[Tuple[str, str], Any] = {}
        self._indexes_created: Dict[Tuple[str, str], bool] = {}

    @property
    @abstractmethod
    def collection_name(self) -> str:
        """Name of the MongoDB collection."""
        ...

    @property
    def database_key(self) -> Optional[str]:
        """
        Explicit database name to use.

        - If set (e.g., 'core', 'smart_data'): always connects to that database.
        - If None (default): uses the current session state,
          making this repository state-scoped (different database per request state).
        """
        return None

    @property
    def database_name(self) -> str:
        """
        Resolved database name.

        Uses database_key if set. Otherwise reads the current session state
        (set automatically by the framework at every entry point).

        Raises:
            ValueError: If database_key is None and session state is not set.
        """
        if self.database_key is not None:
            return self.database_key

        session = get_session()
        if not session or not session.state:
            raise ValueError(
                f"{self.__class__.__name__}: 'state' is required in session but not set. "
                f"Set database_key to a fixed value, or ensure session is initialized."
            )
        return session.state

    @property
    def is_external(self) -> bool:
        """Whether this repository uses an external MongoDB cluster. Default: False."""
        return False

    @property
    def statuses(self) -> Optional[List[str]]:
        """
        The values this record's `status` can take.

        Every entity carries one, and the same two by default, so a listing can
        show the state of anything without knowing what it is looking at. A
        repository with its own lifecycle declares it:

            class UserRepository(Repository):
                @property
                def statuses(self):
                    return ["active", "pending", "inactive"]

        A write with a value outside this set is refused, not stored: an
        unexpected status reaches a panel as an unknown label and a query as a
        silent mismatch.

        None for collections where a lifecycle makes no sense — sessions, tokens,
        counters.
        """
        return list(DEFAULT_STATUSES)

    @property
    def status_field(self) -> str:
        """Cómo se llama el campo que lleva el ciclo de vida del registro.

        `status` por defecto. Se cambia cuando una colección ya usa ese nombre
        para otra cosa y migrarla no vale la pena: los 1,2 millones de empresas
        traen el estado del registro del estado en `status`, y 5,7 millones de
        parcels podrían traer otro. Renombrar en la base es lo más limpio cuando
        se puede; cuando no, se le dice al framework dónde escribir el suyo.

            class ParcelRepository(Repository):
                @property
                def status_field(self):
                    return "lifecycle_status"

        Las dos cosas son independientes: `statuses` dice qué valores valen, esto
        dice dónde se guardan.
        """
        return STATUS

    @property
    def default_status(self) -> Optional[str]:
        """What a record gets when nobody says otherwise. First of `statuses`."""
        declared = self.statuses
        return declared[0] if declared else None

    @property
    def audit(self) -> bool:
        """
        Whether writes carry created_at/created_by/updated_at/updated_by.

        On by default, so a record always answers who last touched it and when
        without any repository having to fill it in. The author is a person when
        a request carries a token, and the process itself otherwise.

        Turn it off only where the stamp would be noise: collections that already
        are a log of who did what (sessions, tokens), or raw scraped data written
        in bulk where the author is always the same process.

            class TokenRepository(Repository):
                audit = False
        """
        return True

    @property
    def cluster_name(self) -> Optional[str]:
        """
        Name of the external cluster to use.
        Required when is_external=True. Must match a name defined
        in the EXTERNAL_MONGODB_CONNECTIONS environment variable.
        """
        return None

    @property
    def indexes(self) -> List[Dict[str, Any]]:
        """
        List of index definitions to create automatically on first collection access.

        Each item is a dict with a required 'key' field and optional Motor kwargs.

        Example:
            return [
                {"key": [("field", 1)]},                               # simple ASC
                {"key": [("field", -1)]},                              # simple DESC
                {"key": [("f1", 1), ("f2", -1)], "unique": True},     # compound + unique
                {"key": [("expires_at", 1)], "expireAfterSeconds": 0}, # TTL index
            ]

        The 'key' value follows pymongo format: list of (field, direction) tuples.
        Any additional keys are passed as kwargs to collection.create_index().
        'background' defaults to True if not specified.
        """
        return []

    @property
    def collection(self):
        """
        Lazy-loaded reference to the Motor collection.

        Resolves the collection from MongoManager (main cluster) or
        ExternalMongoManager (external cluster) based on is_external.
        The database is resolved via database_name (which reads database_key
        or the session state).

        Collections are cached per (database_name, collection_name) key,
        so state-scoped repositories resolve the correct collection for each
        request state without cross-contamination between requests.

        Index creation is NOT triggered here: indexes are created exclusively
        by the index-sync Lambda (see ensure_indexes), so request-time access
        carries no index-creation overhead.
        """
        key = (self.database_name, self.collection_name)

        if key not in self._collection_cache:
            if self.is_external:
                if not self.cluster_name:
                    raise ValueError(
                        f"{self.__class__.__name__}: 'cluster_name' is required when is_external=True"
                    )
                db = ExternalMongoManager.get_database(self.cluster_name, self.database_name)
            else:
                db = MongoManager.get_database(self.database_name)

            collection = db[self.collection_name]
            # La envoltura completa las escrituras; todo lo demás pasa de largo.
            self._collection_cache[key] = (
                AuditedCollection(
                    collection, self.statuses, self.default_status, self.status_field
                )
                if self.audit
                else collection
            )

        return self._collection_cache[key]

    async def page(
        self,
        query: Optional[Dict[str, Any]] = None,
        *,
        sort: Optional[List[tuple]] = None,
        skip: int = 0,
        limit: int = 50,
        projection: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """A page of this collection and how many there are in total.

        The count is a separate query and not a `$facet`: counting a filtered
        million is expensive, and putting it in the same pipeline makes the page
        wait for the count.

        With no filter the total is **estimated**, which reads collection
        metadata instead of the documents. Over a large collection that is the
        difference between instant and a second full read, and the number is only
        there to draw a paginator — nobody needs to know there are exactly
        1,221,736 rather than about that.
        """
        query = query or {}
        cursor = self.collection.find(query, projection)
        if sort:
            cursor = cursor.sort(sort)
        items = await cursor.skip(skip).limit(limit).to_list(length=limit)

        total = (
            await self.collection.count_documents(query)
            if query
            else await self.collection.estimated_document_count()
        )
        return items, total

    async def ensure_indexes(self, database_name: Optional[str] = None):
        """
        Creates all indexes defined in the `indexes` property, blocking until done.

        Args:
            database_name: Target database to create the indexes in.
                - If None (default): uses the resolved database_name
                  (database_key or the current session state).
                - If set: creates the indexes in that specific database. This is
                  used by the index-sync Lambda to create the indexes of a
                  state-scoped repository across every active state database
                  (e.g. 'connecticut', 'new_jersey', ...).

        Index creation is no longer triggered automatically at request time;
        call this explicitly (the index-sync Lambda does) to guarantee creation.

        Idempotent per (database, collection): safe to call multiple times.

        Returns:
            List of created index names (as returned by create_index).
        """
        db_name = database_name or self.database_name
        key = (db_name, self.collection_name)
        if self._indexes_created.get(key):
            return []

        if self.is_external:
            if not self.cluster_name:
                raise ValueError(
                    f"{self.__class__.__name__}: 'cluster_name' is required when is_external=True"
                )
            db = ExternalMongoManager.get_database(self.cluster_name, db_name)
        else:
            db = MongoManager.get_database(db_name)
        collection = db[self.collection_name]

        created: List[str] = []
        for index_def in self.indexes:
            index_key = index_def.get("key")
            if not index_key:
                self.logger.warning(f"Index definition missing 'key': {index_def}")
                continue
            options = {k: v for k, v in index_def.items() if k != "key"}
            options.setdefault("background", True)
            try:
                name = await collection.create_index(index_key, **options)
                created.append(name)
                self.logger.debug(f"Index created on '{db_name}.{self.collection_name}': {index_key}")
            except Exception as e:
                self.logger.error(f"Error creating index {index_key} on '{db_name}': {e}")

        self._indexes_created[key] = True
        return created

    async def prune_orphan_indexes(
        self, database_name: Optional[str] = None, dry_run: bool = True
    ) -> List[str]:
        """
        Detects and (optionally) drops indexes that exist in MongoDB but are NOT
        declared in the `indexes` property — i.e. orphan indexes left behind
        after an index was removed from the code.

        Matching is done by index key spec (fields + direction), never by name,
        since index names are auto-generated by MongoDB. The default '_id_' index
        is always preserved, and special indexes (text/geo/hashed, whose key spec
        MongoDB rewrites internally) are skipped to avoid false positives.

        Args:
            database_name: Target database. Defaults to the resolved
                database_name (database_key or current session state).
            dry_run: If True (default), only reports orphans without dropping.
                If False, drops each orphan index.

        Returns:
            List of orphan index names (dropped when dry_run=False).
        """
        db_name = database_name or self.database_name

        if self.is_external:
            if not self.cluster_name:
                raise ValueError(
                    f"{self.__class__.__name__}: 'cluster_name' is required when is_external=True"
                )
            db = ExternalMongoManager.get_database(self.cluster_name, db_name)
        else:
            db = MongoManager.get_database(db_name)
        collection = db[self.collection_name]

        declared = {
            tuple(tuple(field) for field in index_def["key"])
            for index_def in self.indexes
            if index_def.get("key")
        }

        orphans: List[str] = []
        async for existing in collection.list_indexes():
            name = existing.get("name")
            if name == "_id_":  # the default _id index can never be dropped
                continue

            key_spec = list(existing.get("key", {}).items())
            # Skip special indexes (text/geo/hashed): MongoDB rewrites their key
            # spec ("text"/2dsphere/"hashed", _fts/_ftsx), so a key-based
            # comparison would wrongly flag them as orphans.
            if any(isinstance(direction, str) for _, direction in key_spec) \
                    or any(field in ("_fts", "_ftsx") for field, _ in key_spec):
                continue

            if tuple(key_spec) not in declared:
                orphans.append(name)
                if not dry_run:
                    await collection.drop_index(name)
                    self.logger.info(
                        f"Dropped orphan index '{name}' on '{db_name}.{self.collection_name}'"
                    )
                else:
                    self.logger.info(
                        f"[dry-run] orphan index '{name}' on '{db_name}.{self.collection_name}'"
                    )

        return orphans
