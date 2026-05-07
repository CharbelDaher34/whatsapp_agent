"""Slash-command parsing tests."""
import pytest

from app.services.whatsapp.commands import parse_command


@pytest.mark.parametrize("text,expected", [
    ("/plan", "plan"),
    ("plan", "plan"),
    ("/PLAN", "plan"),
    ("!plan", "plan"),
    ("/usage", "usage"),
    ("quota", "usage"),
    ("/upgrade", "upgrade"),
    ("buy now", "upgrade"),
    ("subscribe", "upgrade"),
    ("/help", "help"),
    ("menu", "help"),
    ("/pro", "pro"),
    ("/max", "max"),
])
def test_command_aliases(text, expected):
    assert parse_command(text) == expected


@pytest.mark.parametrize("text", [
    "",
    "   ",
    "hello there",
    "I want a recipe",
    "/unknownword",
])
def test_non_commands_return_none(text):
    assert parse_command(text) is None
