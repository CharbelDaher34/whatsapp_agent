"""Tool execution context for passing data to tools."""
from contextvars import ContextVar
from typing import Optional

# Context variable to hold the current user's phone during tool execution
_current_phone: ContextVar[Optional[str]] = ContextVar('current_phone', default=None)


def set_current_phone(phone: str) -> None:
    """Set the current phone number for tool context."""
    _current_phone.set(phone)


def get_current_phone() -> Optional[str]:
    """Get the current phone number from tool context."""
    return _current_phone.get()


def clear_current_phone() -> None:
    """Clear the current phone number."""
    _current_phone.set(None)

