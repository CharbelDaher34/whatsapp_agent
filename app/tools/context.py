"""Tool execution context.

Keeps the *current* user info available to tools without threading it
through every call. Set at the start of an agent turn, cleared at the end.
"""
from contextvars import ContextVar
from typing import Optional


_current_phone: ContextVar[Optional[str]] = ContextVar("current_phone", default=None)
_current_user_id: ContextVar[Optional[int]] = ContextVar("current_user_id", default=None)


def set_current_phone(phone: Optional[str]) -> None:
    _current_phone.set(phone)


def get_current_phone() -> Optional[str]:
    return _current_phone.get()


def clear_current_phone() -> None:
    _current_phone.set(None)


def set_current_user_id(user_id: Optional[int]) -> None:
    _current_user_id.set(user_id)


def get_current_user_id() -> Optional[int]:
    return _current_user_id.get()


def clear_current_user_id() -> None:
    _current_user_id.set(None)
