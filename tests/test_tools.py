"""Tool unit tests."""
import json

import pytest

from app.models.user import User
from app.tools.builtin.ask_user import AskButtonsTool, AskListTool
from app.tools.builtin.calculator import CalculatorTool
from app.tools.registry import init_tools, get_tools_for_user


@pytest.mark.asyncio
async def test_calculator_handles_arithmetic():
    tool = CalculatorTool()
    assert "result is: 12" in await tool.process("3 * 4")
    assert "result is: 7" in await tool.process("(2 + 5)")
    assert "result is: 8" in await tool.process("2 ** 3")


@pytest.mark.asyncio
async def test_calculator_rejects_unsafe_input():
    tool = CalculatorTool()
    out = await tool.process("__import__('os').system('ls')")
    assert "couldn't parse" in out.lower() or "error" in out.lower()


@pytest.mark.asyncio
async def test_calculator_division_by_zero():
    tool = CalculatorTool()
    assert "division by zero" in (await tool.process("1 / 0")).lower()


@pytest.mark.asyncio
async def test_ask_buttons_validates_input():
    tool = AskButtonsTool()
    # Missing phone in context
    out = await tool.process(json.dumps({"prompt": "?", "options": ["A"]}))
    assert "phone" in out.lower()


@pytest.mark.asyncio
async def test_ask_buttons_requires_json():
    tool = AskButtonsTool()
    out = await tool.process("not json", phone="123")
    assert "json" in out.lower()


@pytest.mark.asyncio
async def test_ask_list_validates_input():
    tool = AskListTool()
    out = await tool.process(json.dumps({}), phone="123")
    assert "items" in out.lower() or "json" in out.lower()


def test_registry_filters_by_plan():
    init_tools()
    free_user = User(phone="1", subscription_tier="free")
    pro_user = User(phone="2", subscription_tier="pro")
    max_user = User(phone="3", subscription_tier="max")

    free_names = {t.name for t in get_tools_for_user(free_user)}
    pro_names = {t.name for t in get_tools_for_user(pro_user)}
    max_names = {t.name for t in get_tools_for_user(max_user)}

    assert "calculator" in free_names
    assert "ask_buttons" in free_names
    assert "text_to_image" not in free_names
    assert "image_to_image" not in free_names

    assert "text_to_image" in pro_names
    assert "image_to_image" in pro_names

    assert "text_to_image" in max_names
    assert max_names >= pro_names
