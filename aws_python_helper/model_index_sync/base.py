"""
ModelIndexSyncLambda - Synchronizes MongoDB indexes for a service's repositories.

Creates (idempotently) every index declared in the service's repositories, in
the correct databases:
  - Repositories with a fixed database_key (e.g. 'core') → that database.
  - State-scoped repositories (database_key is None) → every active state
    database, read from core.states (is_active=True). A state-scoped collection
    (e.g. 'parcels') therefore gets its indexes created in 'connecticut',
    'new_jersey', etc.

Designed to run once per deploy (and on demand), guaranteeing index creation
without the per-request overhead of creating indexes at runtime.

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

Response (via Lambda base run()):
    {"success": True, "data": [
        {"repository": "ParcelsRepository", "database": "connecticut",
         "collection": "parcels", "indexes": ["parcel_id_1", ...]},
        {"repository": "UsersRepository", "database": "core",
         "collection": "users", "indexes": ["email_1"]},
        ...
    ]}
"""

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

    async def process(self) -> Any:
        active_states = await self._active_states()
        report: List[dict] = []

        for repo_cls in self.repositories:
            repo = repo_cls()
            # database_key is None -> state-scoped (collection repeats per state db).
            is_state_scoped = repo.database_key is None and not repo.is_external
            target_databases = active_states if is_state_scoped else [repo.database_name]

            for db_name in target_databases:
                created = await repo.ensure_indexes(database_name=db_name)
                report.append({
                    "repository": repo_cls.__name__,
                    "database": db_name,
                    "collection": repo.collection_name,
                    "indexes": created,
                })

        return report
