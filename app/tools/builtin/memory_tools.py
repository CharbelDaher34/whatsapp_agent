"""Tools that let the assistant manage a user's long-term memory.

Three tools:
- ``remember``: store a key/value fact (or unkeyed preference).
- ``recall``: search the user's memories.
- ``forget``: delete a memory by key/substring.

Tool input is JSON for ``remember``/``forget``; plain text for ``recall``.
"""
import json
from typing import Any, Optional

from app.core.logging import logger
from app.db.session import get_session
from app.services.memory_service import (
    forget_memory,
    recall as recall_service,
    render_memories,
    upsert_memory,
)
from app.tools.base import BaseTool


def _parse_json(text: str) -> Optional[dict]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


class RememberTool(BaseTool):
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="remember",
            description="Store a long-term fact or preference about the user.",
            capabilities=(
                "Use sparingly: only store stable facts the user shares (name, location, "
                "timezone, preferences, ongoing projects). Don't store transient or "
                "private financial details. "
                'Input MUST be JSON: {"kind": "fact|preference", "key": "<short>", '
                '"value": "<text>", "importance": 0.7}. "key" optional for preferences.'
            ),
            enabled=enabled,
            min_tier="free",
        )

    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        user_id = kwargs.get("user_id")
        if not user_id:
            return "remember failed: no user context."
        data = _parse_json(text) or {}
        kind = (data.get("kind") or "fact").strip().lower()
        if kind not in ("fact", "preference"):
            kind = "fact"
        key = (data.get("key") or "").strip() or None
        value = (data.get("value") or "").strip()
        if not value:
            return (
                "remember requires JSON like "
                '{"kind":"fact","key":"name","value":"Alex","importance":0.8}.'
            )
        try:
            importance = float(data.get("importance", 0.6))
        except (TypeError, ValueError):
            importance = 0.6
        importance = max(0.0, min(1.0, importance))

        async with get_session() as session:
            row = await upsert_memory(
                session, user_id, kind, value,
                key=key, importance=importance, source="tool",
            )
            await session.commit()
            logger.info(f"🧠 Saved memory id={row.id} kind={kind} key={key}")
        return f"Saved memory ({kind}): {key + '=' if key else ''}{value}"


class RecallTool(BaseTool):
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="recall",
            description="Search what you remember about this user.",
            capabilities=(
                "Pass a free-text query (e.g. 'timezone' or 'pizza preferences'). "
                "Returns up to 8 matching memories plus the latest summary."
            ),
            enabled=enabled,
            min_tier="free",
        )

    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        user_id = kwargs.get("user_id")
        if not user_id:
            return "recall failed: no user context."
        query = (text or "").strip() or None
        async with get_session() as session:
            rows = await recall_service(session, user_id, query, limit=8)
        if not rows:
            return "I have no memories on file for this user."
        return render_memories(rows)


class ForgetTool(BaseTool):
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="forget",
            description="Delete a memory you previously stored.",
            capabilities=(
                'Input is JSON: {"key": "<substring of key>"} OR {"id": <memory_id>}. '
                "Deletes all matching memories for this user."
            ),
            enabled=enabled,
            min_tier="free",
        )

    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        user_id = kwargs.get("user_id")
        if not user_id:
            return "forget failed: no user context."
        data = _parse_json(text) or {}
        key = data.get("key")
        memory_id = data.get("id")
        if not key and not memory_id:
            return 'forget requires {"key": "..."} or {"id": <int>}.'
        async with get_session() as session:
            removed = await forget_memory(
                session, user_id,
                key=str(key) if key else None,
                memory_id=int(memory_id) if memory_id else None,
            )
            await session.commit()
        return f"Removed {removed} memory record(s)." if removed else "No matching memory."
