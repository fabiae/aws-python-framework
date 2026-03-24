"""
Repository Base - Base class for all MongoDB repository classes.

Eliminates boilerplate by providing automatic connection management,
collection access, and index creation without requiring the user to
pass a database connection or call any initialization method.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from ..database.mongo_manager import MongoManager
from ..database.external_mongo_manager import ExternalMongoManager
from ..context.state import get_state


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
            - If None (default): uses the constitution-state contextvar automatically.
              This makes the repository "state-scoped" — it connects to the database
              matching the current request state (e.g., 'connecticut', 'new_jersey').
        is_external (bool): Whether to use an external MongoDB cluster. Default: False.
        cluster_name (str): External cluster name. Required if is_external=True.
        indexes (list): List of index definitions to create automatically.

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

        # State-scoped repository — connects to the current constitution-state database
        class LandRecordsRepository(Repository):

            @property
            def collection_name(self):
                return "land_records"
            # No database_key → uses get_state() automatically

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
        - If None (default): uses the current constitution-state contextvar,
          making this repository state-scoped (different database per request state).
        """
        return None

    @property
    def database_name(self) -> str:
        """
        Resolved database name.

        Uses database_key if set. Otherwise reads the current constitution-state
        from the contextvar (set automatically by the framework at every entry point).

        Raises:
            ValueError: If database_key is None and constitution-state is not set in context.
        """
        if self.database_key is not None:
            return self.database_key

        state = get_state()
        if not state:
            raise ValueError(
                f"{self.__class__.__name__}: 'constitution-state' is required but not set in context. "
                f"Set database_key to a fixed value, or ensure constitution-state is passed in the request."
            )
        return state

    @property
    def is_external(self) -> bool:
        """Whether this repository uses an external MongoDB cluster. Default: False."""
        return False

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
        or the constitution-state contextvar).

        Collections are cached per (database_name, collection_name) key,
        so state-scoped repositories resolve the correct collection for each
        request state without cross-contamination between requests.

        On first access for a given key, schedules index creation as a
        background asyncio task so indexes are created without blocking the caller.
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

            self._collection_cache[key] = db[self.collection_name]

            # Schedule index creation as a background task on the running event loop.
            if self.indexes and not self._indexes_created.get(key):
                try:
                    asyncio.get_running_loop().create_task(self.ensure_indexes())
                except RuntimeError:
                    pass  # No running event loop (e.g. synchronous test context)

        return self._collection_cache[key]

    async def ensure_indexes(self):
        """
        Creates all indexes defined in the `indexes` property.

        Called automatically in background on first collection access.
        Can also be called explicitly at the start of a method when index
        creation must be guaranteed to complete before proceeding.

        Idempotent: safe to call multiple times, only runs once per (database, collection).
        """
        key = (self.database_name, self.collection_name)
        if self._indexes_created.get(key):
            return

        for index_def in self.indexes:
            index_key = index_def.get("key")
            if not index_key:
                self.logger.warning(f"Index definition missing 'key': {index_def}")
                continue
            options = {k: v for k, v in index_def.items() if k != "key"}
            options.setdefault("background", True)
            try:
                await self.collection.create_index(index_key, **options)
                self.logger.debug(f"Index created: {index_key}")
            except Exception as e:
                self.logger.error(f"Error creating index {index_key}: {e}")

        self._indexes_created[key] = True
