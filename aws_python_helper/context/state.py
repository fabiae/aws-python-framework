"""
Constitution State Context - Manages request-scoped state for multi-state database routing.

Uses Python's contextvars to propagate the current constitution-state across async call chains.
Set automatically by the framework at every entry point (API, Lambda, SQS Consumer, Fargate Task).
Read automatically by state-scoped repositories (database_key = None) to resolve the target database.
"""

from contextvars import ContextVar
from typing import Optional

_constitution_state: ContextVar[Optional[str]] = ContextVar('constitution_state', default=None)


def get_state() -> Optional[str]:
    """Get the current constitution state from async context."""
    return _constitution_state.get()


def set_state(state: str) -> None:
    """Set the current constitution state in async context."""
    _constitution_state.set(state)
