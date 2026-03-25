"""
Session Context - Manages request-scoped session for cross-service propagation.

Uses Python's contextvars to propagate the current session across async call chains.
Set automatically by the framework at every entry point (API, Lambda, SQS Consumer, Fargate Task).

The Session object holds:
    - state: Constitution state for multi-state database routing
    - user: Authenticated user data (from auth middleware)
    - Extensible for future properties
"""

from contextvars import ContextVar
from typing import Dict, Any, Optional


class Session:
    """
    Request-scoped session that propagates across all service types.

    Contains contextual data (state, user, etc.) that is automatically
    propagated through SNS messages, SQS records, Fargate env vars,
    and Lambda events.
    """

    SENSITIVE_FIELDS = ('password', 'hashed_password')

    def __init__(self, state: Optional[str] = None, user: Optional[Dict[str, Any]] = None):
        self._state = state
        self._user = None
        if user is not None:
            self.user = user

    @property
    def state(self) -> Optional[str]:
        """Constitution state for database routing"""
        return self._state

    @state.setter
    def state(self, value: str):
        self._state = value

    @property
    def user(self) -> Optional[Dict[str, Any]]:
        """Authenticated user data"""
        return self._user

    @user.setter
    def user(self, value: Optional[Dict[str, Any]]):
        if isinstance(value, dict):
            value = {k: v for k, v in value.items() if k not in self.SENSITIVE_FIELDS}
        self._user = value

    def to_dict(self) -> dict:
        """Serialize session to dict (only non-None properties)"""
        result = {}
        if self._state is not None:
            result['state'] = self._state
        if self._user is not None:
            result['user'] = self._user
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'Session':
        """Reconstruct Session from dict"""
        if not isinstance(data, dict):
            return cls()
        return cls(
            state=data.get('state'),
            user=data.get('user'),
        )


_session: ContextVar[Optional[Session]] = ContextVar('session', default=None)


def get_session() -> Session:
    """Get the current session from async context. Creates one if not set."""
    session = _session.get()
    if session is None:
        session = Session()
        _session.set(session)
    return session


def set_session(session: Session) -> None:
    """Set the current session in async context."""
    _session.set(session)
