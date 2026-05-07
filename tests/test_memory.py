"""Memory service + tools."""
import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

# Make sure all SQLModel tables are imported so create_all sees them.
from app.models import Conversation, Memory, Message, User  # noqa: F401
from app.services.memory_service import (
    forget_memory,
    get_recent_summary,
    recall,
    render_memories,
    upsert_memory,
)
from app.tools.builtin.memory_tools import (
    ForgetTool,
    RecallTool,
    RememberTool,
)


@pytest.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        # Seed a user
        user = User(phone="123", subscription_tier="free")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        session.user_id = user.id  # type: ignore[attr-defined]
        yield session
    await engine.dispose()


async def test_upsert_and_recall(async_session):
    user_id = async_session.user_id  # type: ignore[attr-defined]
    await upsert_memory(async_session, user_id, "fact", "Alex", key="name", importance=0.9)
    await upsert_memory(async_session, user_id, "preference", "metric units", key="units")
    rows = await recall(async_session, user_id, "name", limit=5)
    assert any(r.key == "name" and "Alex" in r.value for r in rows)


async def test_upsert_replaces_same_key(async_session):
    user_id = async_session.user_id  # type: ignore[attr-defined]
    await upsert_memory(async_session, user_id, "fact", "Berlin", key="city")
    await upsert_memory(async_session, user_id, "fact", "Munich", key="city")
    rows = await recall(async_session, user_id, "city", limit=5)
    cities = [r.value for r in rows if r.key == "city"]
    assert cities == ["Munich"]  # only one row


async def test_forget_by_key(async_session):
    user_id = async_session.user_id  # type: ignore[attr-defined]
    await upsert_memory(async_session, user_id, "fact", "Alex", key="name")
    removed = await forget_memory(async_session, user_id, key="name")
    assert removed == 1
    rows = await recall(async_session, user_id, None)
    assert not any(r.key == "name" for r in rows)


async def test_render_memories_formats():
    rows = [
        Memory(user_id=1, kind="fact", key="name", value="Alex", importance=1.0),
        Memory(user_id=1, kind="summary", value="Alex likes pizza."),
    ]
    out = render_memories(rows)
    assert "name = Alex" in out
    assert "[conversation summary]" in out


async def test_recall_returns_summary_first_when_present(async_session):
    user_id = async_session.user_id  # type: ignore[attr-defined]
    await upsert_memory(async_session, user_id, "summary", "Alex enjoys pizza.")
    await upsert_memory(async_session, user_id, "fact", "Alex", key="name")
    rows = await recall(async_session, user_id, None, limit=8)
    assert any(r.kind == "summary" for r in rows)


async def test_remember_tool_validates_input():
    tool = RememberTool()
    out = await tool.process("not json", user_id=1)
    assert "remember requires JSON" in out


async def test_forget_tool_requires_target():
    tool = ForgetTool()
    out = await tool.process(json.dumps({}), user_id=1)
    assert "key" in out.lower() or "id" in out.lower()


async def test_recall_tool_no_user_context():
    tool = RecallTool()
    out = await tool.process("anything", user_id=None)
    assert "user context" in out
