import time
from typing import Dict, Tuple


class InvalidStateError(Exception):
    """Raised when a state is not found or not active in the database."""
    pass


class StateValidator:
    """
    Validates that a state exists and is active in the core.states collection.

    A state counts as active with either `status: "active"` or `is_active: True`.
    The boolean is what every service has written until now; the status is what
    the region catalog replicates. Accepting both means the boolean can be
    dropped once no service reads it, without a flag day.

    Uses an in-memory cache with a 5-minute TTL to avoid querying the database
    on every request. A rejection is cached too, for far less time: the point of
    not caching it was that a state activated a minute ago should start working
    at once, and thirty seconds keeps that while taking the database out of the
    path. It used to be the other way around — only valid states were cached, so
    the most common rejection, a panel pointed at a state where this service is
    not active, queried core.states on *every* request, and every card on a
    screen paid for it. The slowest path was the one taken most.
    """

    _cache: Dict[str, float] = {}  # state -> timestamp when cached
    _rejected: Dict[str, float] = {}  # state -> timestamp when rejected
    _CACHE_TTL: int = 300  # 5 minutes
    # Lo que se le perdona a un rechazo. Corto a propósito: es el techo de lo que
    # un estado recién activado puede tardar en empezar a andar.
    _REJECT_TTL: int = 30

    @classmethod
    async def validate(cls, state: str):
        """
        Validate that state exists in core.states and is active.

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

        if state in cls._rejected:
            if now - cls._rejected[state] < cls._REJECT_TTL:
                raise InvalidStateError(f"State '{state}' is not valid or not active")
            del cls._rejected[state]

        from ..database.mongo_manager import MongoManager
        db = MongoManager.get_database('core')
        doc = await db.states.find_one({
            "name": state,
            "$or": [{"status": "active"}, {"is_active": True}],
        })

        if doc:
            cls._cache[state] = now
            cls._rejected.pop(state, None)
            return

        cls._rejected[state] = now
        raise InvalidStateError(f"State '{state}' is not valid or not active")

    @classmethod
    def clear_cache(cls):
        """Clear the state validation cache, both what passed and what did not."""
        cls._cache.clear()
        cls._rejected.clear()
