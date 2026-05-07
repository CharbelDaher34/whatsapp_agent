"""Per-user memory store.

Three kinds of memory live in the same table so we can rank them uniformly:

- ``fact``: structured key/value the assistant (or the user) recorded
  via the ``remember`` tool — e.g. ``name=Alex``, ``timezone=Europe/Berlin``.
- ``preference``: free-form preferences the user repeatedly expressed —
  e.g. ``prefers metric units``.
- ``summary``: a compressed recap of older conversation turns produced by
  lazy summarization once the rolling history grows past plan depth.
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Memory(SQLModel, table=True):
    __tablename__ = "memory"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    kind: str = Field(default="fact", index=True)  # fact | preference | summary
    key: Optional[str] = Field(default=None, index=True)  # nullable for summaries
    value: str
    importance: float = Field(default=0.5)  # 0..1, higher = surfaces sooner
    source: str = Field(default="auto")  # auto | tool | manual

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
