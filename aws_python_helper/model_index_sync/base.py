"""
ModelIndexSyncLambda - Synchronizes MongoDB indexes for a service's repositories.

Creates (idempotently) every index declared in the service's repositories, in
the correct databases:
  - Repositories with a fixed database_key (e.g. 'core') → that database.
  - State-scoped repositories (database_key is None) → every active state
    database, read from core.states (is_active=True). A state-scoped collection
    (e.g. 'parcels') therefore gets its indexes created in 'connecticut',
    'new_jersey', etc.

It also prunes orphan indexes: any index present in MongoDB but no longer
declared in a repository's `indexes` is dropped (see Repository.prune_orphan_indexes).

Designed to run once per deploy (and on demand), guaranteeing index creation
without the per-request overhead of creating indexes at runtime.

Each (collection, database) unit is synced concurrently (bounded by
`max_concurrency`); index creation WITHIN a unit stays sequential. A failure in
one unit is captured and never aborts the others, so a single broken collection
does not stop the rest of the sync — the failure is reported instead.

Usage — subclass and declare the repositories to sync:

    import aws_python_helper
    from repositories.parcels import ParcelsRepository
    from repositories.users import UsersRepository

    class PropertiesModelIndexSyncLambda(aws_python_helper.ModelIndexSyncLambda):
        @property
        def repositories(self) -> list:
            return [ParcelsRepository, UsersRepository]

This Lambda does not require a session state (requires_state = False); it
operates across all active states.

Response (via Lambda base run()) — always success=True at the top level; per-unit
outcome is reported in results[].success:
    {"success": True, "data": {
        "summary": {"total": 3, "succeeded": 2, "failed": 1},
        "results": [
            {"repository": "ParcelsRepository", "database": "connecticut",
             "collection": "parcels", "indexes": ["parcel_id_1", ...],
             "orphan_indexes_dropped": ["old_field_1"], "success": True},
            {"repository": "UsersRepository", "database": "core",
             "collection": "users", "indexes": ["email_1"],
             "orphan_indexes_dropped": [], "success": True},
            {"repository": "TokensRepository", "database": "core",
             "collection": "tokens", "indexes": [], "orphan_indexes_dropped": [],
             "success": False, "error": "..."},
        ]
    }}
"""

import asyncio
from typing import Any, List, Type

from ..lambda_standalone.base import Lambda
from ..repository.base import Repository
from ..database.mongo_manager import MongoManager


class ModelIndexSyncLambda(Lambda):
    """
    Base class for index-synchronization Lambdas.

    Subclass and override `repositories` to declare which repositories to sync.
    Everything else (resolving core vs state-scoped, reading active states and
    creating the indexes) is handled automatically.
    """

    @property
    def requires_state(self) -> bool:
        # Operates across all states; not tied to a single one.
        return False

    @property
    def repositories(self) -> List[Type[Repository]]:
        """
        Repositories whose indexes should be synchronized.

        Override returning a list of Repository subclasses (the classes, not
        instances). Declare them explicitly rather than auto-discovering, so the
        synced set is intentional and nothing is silently missed or added.
        """
        return []

    @property
    def states_database(self) -> str:
        """Database holding the states collection. Default: 'core'."""
        return "core"

    @property
    def states_collection(self) -> str:
        """Collection listing the states. Default: 'states'."""
        return "states"

    @property
    def max_concurrency(self) -> int:
        """
        Max number of (collection, database) index syncs running in parallel.
        0 (or negative) means unlimited. Default: 10.
        """
        return 10

    async def validate(self):
        if not self.repositories:
            raise ValueError(
                "repositories is not configured on this ModelIndexSyncLambda"
            )

    async def _active_states(self) -> List[str]:
        """Names of active states — i.e. the state-scoped database names."""
        db = MongoManager.get_database(self.states_database)
        cursor = db[self.states_collection].find(
            {"is_active": True}, {"name": 1, "_id": 0}
        )
        return [doc["name"] async for doc in cursor if doc.get("name")]

    async def _sync_target(self, repo_cls: Type[Repository], db_name: str) -> dict:
        """
        Sync one collection in one database: create declared indexes and drop
        orphan ones.

        Captures its own errors so a single failure never aborts the rest of the
        sync — a failed unit returns success=False with the error message, and
        any indexes created before the failure are still reported.
        """
        result = {
            "repository": repo_cls.__name__,
            "database": db_name,
            "collection": None,
            "indexes": [],
            "orphan_indexes_dropped": [],
            "success": True,
        }
        try:
            repo = repo_cls()
            result["collection"] = repo.collection_name
            result["indexes"] = await repo.ensure_indexes(database_name=db_name)
            result["orphan_indexes_dropped"] = await repo.prune_orphan_indexes(
                database_name=db_name, dry_run=False
            )
        except Exception as e:
            self.logger.error(
                f"Index sync failed for {repo_cls.__name__} on '{db_name}': {e}"
            )
            result["success"] = False
            result["error"] = str(e)
        return result

    async def process(self) -> Any:
        active_states = await self._active_states()

        # Plan all independent (repo_cls, db_name) work units.
        targets: List[tuple] = []
        for repo_cls in self.repositories:
            repo = repo_cls()
            # database_key is None -> state-scoped (collection repeats per state db).
            is_state_scoped = repo.database_key is None and not repo.is_external
            target_databases = active_states if is_state_scoped else [repo.database_name]
            for db_name in target_databases:
                targets.append((repo_cls, db_name))

        # Each (collection, database) runs concurrently; index creation WITHIN
        # each one stays sequential (via await). _sync_target captures its own
        # errors, so one failed unit never aborts the others.
        limit = self.max_concurrency
        if limit and limit > 0:
            semaphore = asyncio.Semaphore(limit)

            async def run(repo_cls, db_name):
                async with semaphore:
                    return await self._sync_target(repo_cls, db_name)
        else:
            async def run(repo_cls, db_name):
                return await self._sync_target(repo_cls, db_name)

        results = list(await asyncio.gather(
            *(run(repo_cls, db_name) for repo_cls, db_name in targets)
        ))

        failed = [r for r in results if not r["success"]]
        return {
            "summary": {
                "total": len(results),
                "succeeded": len(results) - len(failed),
                "failed": len(failed),
            },
            "results": results,
        }
