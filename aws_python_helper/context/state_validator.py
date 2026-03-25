import time
from typing import Dict, Tuple


class InvalidStateError(Exception):
    """Raised when a state is not found or not active in the database."""
    pass


class StateValidator:
    """
    Validates that a state exists and is active in the core.states collection.

    Uses an in-memory cache with a 5-minute TTL to avoid querying the database
    on every request. Only valid (active) states are cached — invalid states
    always hit the database so that recently activated states are picked up
    immediately.
    """

    _cache: Dict[str, float] = {}  # state -> timestamp when cached
    _CACHE_TTL: int = 300  # 5 minutes

    @classmethod
    async def validate(cls, state: str):
        """
        Validate that state exists in core.states with is_active=True.

        Args:
            state: The state name to validate

        Raises:
            InvalidStateError: If the state doesn't exist or is not active
        """
        now = time.time()

        if state in cls._cache:
            if now - cls._cache[state] < cls._CACHE_TTL:
                return
            del cls._cache[state]

        from ..database.mongo_manager import MongoManager
        db = MongoManager.get_database('core')
        doc = await db.states.find_one({"name": state, "is_active": True})

        if doc:
            cls._cache[state] = now
            return

        raise InvalidStateError(f"State '{state}' is not valid or not active")

    @classmethod
    def clear_cache(cls):
        """Clear the state validation cache."""
        cls._cache.clear()
