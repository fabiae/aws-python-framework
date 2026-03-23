"""
Repository Base - Base class for all MongoDB repository classes.

Eliminates boilerplate by providing automatic connection management,
collection access, and index creation without requiring the user to
pass a database connection or call any initialization method.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..database.mongo_manager import MongoManager
from ..database.external_mongo_manager import ExternalMongoManager


class Repository(ABC):
    """
    Base class for all MongoDB repositories.

    Subclasses only need to declare which collection they use,
    whether it is external, and what indexes to create.
    The connection and index creation are handled automatically.

    Required properties to override:
        collection_name (str): Name of the MongoDB collection.

    Optional properties to override:
        database_name (str): Name of the database. Default: "core".
        is_external (bool): Whether to use an external cluster. Default: False.
        cluster_name (str): External cluster name. Required if is_external=True.
        indexes (list): List of index definitions to create automatically.

    Usage:
        class TownsRepository(Repository):

            @property
            def collection_name(self):
                return "towns"

            @property
            def indexes(self):
                return [
                    {"key": [("name", 1)]},
                    {"key": [("platform", 1)]},
                ]

            async def get_all(self):
                return await self.collection.find({}).to_list(length=None)

        # Instantiate without passing any db connection
        repo = TownsRepository()

    External cluster usage:
        class AddressRepository(Repository):

            @property
            def database_name(self):
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
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._indexes_created = False
        self._collection_ref = None

    @property
    @abstractmethod
    def collection_name(self) -> str:
        """Name of the MongoDB collection."""
        ...

    @property
    def database_name(self) -> str:
        """Name of the MongoDB database. Default: 'core'."""
        return "core"

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

        On first access, schedules index creation as a background asyncio task
        so indexes are created without blocking the caller.
        """
        if self._collection_ref is None:
            if self.is_external:
                if not self.cluster_name:
                    raise ValueError(
                        f"{self.__class__.__name__}: 'cluster_name' is required when is_external=True"
                    )
                db = ExternalMongoManager.get_database(self.cluster_name, self.database_name)
            else:
                db = MongoManager.get_database(self.database_name)

            self._collection_ref = db[self.collection_name]

            # Schedule index creation as a background task on the running event loop.
            # This works because all framework handlers use loop.run_until_complete(),
            # which keeps the loop running while user code executes.
            # create_task() simply adds a coroutine to the existing loop queue
            # without modifying or interrupting it.
            if self.indexes and not self._indexes_created:
                try:
                    asyncio.get_running_loop().create_task(self.ensure_indexes())
                except RuntimeError:
                    pass  # No running event loop (e.g. synchronous test context)

        return self._collection_ref

    async def ensure_indexes(self):
        """
        Creates all indexes defined in the `indexes` property.

        Called automatically in background on first collection access.
        Can also be called explicitly at the start of a method when index
        creation must be guaranteed to complete before proceeding.

        Idempotent: safe to call multiple times, only runs once.
        """
        if self._indexes_created:
            return

        for index_def in self.indexes:
            key = index_def.get("key")
            if not key:
                self.logger.warning(f"Index definition missing 'key': {index_def}")
                continue
            options = {k: v for k, v in index_def.items() if k != "key"}
            options.setdefault("background", True)
            try:
                await self.collection.create_index(key, **options)
                self.logger.debug(f"Index created: {key}")
            except Exception as e:
                self.logger.error(f"Error creating index {key}: {e}")

        self._indexes_created = True
