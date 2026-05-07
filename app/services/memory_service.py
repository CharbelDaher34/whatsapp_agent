"""User memory: persistence, retrieval, and lazy summarization.

API surface:
- ``upsert_memory(user_id, kind, key, value, importance, source)`` — write.
- ``forget_memory(user_id, key|memory_id)`` — delete.
- ``recall(user_id, query, limit)`` — substring-ranked recall, plus the most
  recent summary, plus the highest-importance facts. Cheap and good enough
  until we add embeddings.
- ``get_recent_summary(user_id)`` — single most recent summary.
- ``maybe_summarize(user_id, conversation, plan)`` — invoked from the
  orchestrator after each turn; if the visible history exceeds ``2 *
  plan.history_depth``, distil the older half into a summary memory.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.core.plans import PlanLimits
from app.models.conversation import Conversation
from app.models.memory import Memory
from app.models.message import Message


_MAX_SUMMARY_CHARS = 1500


async def upsert_memory(
    session: AsyncSession,
    user_id: int,
    kind: str,
    value: str,
    *,
    key: Optional[str] = None,
    importance: float = 0.5,
    source: str = "tool",
) -> Memory:
    """Upsert a memory keyed on (user_id, kind, key) when ``key`` is set;
    otherwise always insert (e.g. summaries which have no stable key)."""
    if key is not None:
        result = await session.execute(
            select(Memory).where(
                Memory.user_id == user_id,
                Memory.kind == kind,
                Memory.key == key,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
            existing.importance = max(existing.importance, importance)
            existing.source = source
            existing.updated_at = datetime.utcnow()
            session.add(existing)
            await session.flush()
            return existing

    row = Memory(
        user_id=user_id, kind=kind, key=key, value=value,
        importance=importance, source=source,
    )
    session.add(row)
    await session.flush()
    return row


async def forget_memory(
    session: AsyncSession,
    user_id: int,
    *,
    key: Optional[str] = None,
    memory_id: Optional[int] = None,
) -> int:
    """Delete by key (case-insensitive contains) or id. Returns rows removed."""
    if not key and not memory_id:
        return 0
    conditions = [Memory.user_id == user_id]
    if memory_id is not None:
        conditions.append(Memory.id == memory_id)
    if key:
        conditions.append(Memory.key.ilike(f"%{key}%"))  # type: ignore[attr-defined]
    result = await session.execute(delete(Memory).where(*conditions))
    return result.rowcount or 0


async def recall(
    session: AsyncSession,
    user_id: int,
    query: Optional[str] = None,
    *,
    limit: int = 8,
) -> List[Memory]:
    """Return the most relevant memories for ``user_id``.

    Order: matches on key/value first, then high importance, then recency.
    Always includes the latest summary so the model has long-range context.
    """
    stmt = select(Memory).where(Memory.user_id == user_id)
    if query:
        like = f"%{query.lower()}%"
        stmt = stmt.where(
            or_(
                Memory.key.ilike(like),  # type: ignore[attr-defined]
                Memory.value.ilike(like),  # type: ignore[attr-defined]
            )
        )
    stmt = stmt.order_by(
        Memory.importance.desc(), Memory.updated_at.desc(),
    ).limit(limit)
    rows = list((await session.execute(stmt)).scalars().all())

    # Always prepend the latest summary if it isn't already in the result.
    summary = await get_recent_summary(session, user_id)
    if summary and summary.id not in {r.id for r in rows}:
        rows = [summary] + rows[: max(0, limit - 1)]
    return rows


async def get_recent_summary(session: AsyncSession, user_id: int) -> Optional[Memory]:
    result = await session.execute(
        select(Memory)
        .where(Memory.user_id == user_id, Memory.kind == "summary")
        .order_by(Memory.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def render_memories(memories: List[Memory]) -> str:
    """Compact bullet list for inclusion in the system prompt."""
    if not memories:
        return ""
    lines = []
    for m in memories:
        if m.kind == "summary":
            lines.append(f"• [conversation summary] {m.value}")
        elif m.key:
            lines.append(f"• [{m.kind}] {m.key} = {m.value}")
        else:
            lines.append(f"• [{m.kind}] {m.value}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Lazy summarization
# ---------------------------------------------------------------------------

async def maybe_summarize(
    session: AsyncSession,
    user_id: int,
    conversation: Conversation,
    plan: PlanLimits,
) -> Optional[Memory]:
    """If history is large, distil the oldest half into a summary.

    Skip on the Free plan (cost) and when below threshold. Uses the same
    OpenAI key configured for the agent; on any failure we silently bail —
    summaries are nice-to-have, not load-bearing.
    """
    if plan.name == "free":
        return None
    if not settings.OPENAI_API_KEY:
        return None

    threshold = max(20, plan.history_depth * 2)
    summary = await get_recent_summary(session, user_id)
    cutoff = summary.created_at if summary else None

    history_stmt = select(Message).where(Message.conversation_id == conversation.id)
    if cutoff:
        history_stmt = history_stmt.where(Message.created_at > cutoff)
    history_stmt = history_stmt.order_by(Message.created_at.asc())
    rows = list((await session.execute(history_stmt)).scalars().all())
    if len(rows) < threshold:
        return None

    older = rows[: len(rows) // 2]
    if not older:
        return None

    transcript = "\n".join(f"{m.sender}: {m.content[:600]}" for m in older)[:8000]
    new_summary = await _summarize_with_openai(transcript)
    if not new_summary:
        return None

    return await upsert_memory(
        session, user_id,
        kind="summary",
        value=new_summary[:_MAX_SUMMARY_CHARS],
        importance=0.9,
        source="auto",
    )


async def _summarize_with_openai(transcript: str) -> Optional[str]:
    try:
        from openai import AsyncOpenAI  # type: ignore
    except ImportError:
        return None
    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        result = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarize the following WhatsApp conversation between a user "
                        "and an assistant in 4-8 short bullet points. Capture: stable "
                        "facts about the user (name, location, preferences, ongoing "
                        "projects), unresolved questions, and any commitments made by "
                        "the assistant. Do NOT include greetings or filler."
                    ),
                },
                {"role": "user", "content": transcript},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        return (result.choices[0].message.content or "").strip() or None
    except Exception as e:
        logger.warning(f"Memory summarization failed: {e}")
        return None
