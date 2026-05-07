"""Usage tracking model for plan-based quotas."""
from datetime import datetime, date
from typing import Optional

from sqlmodel import SQLModel, Field


class UsageRecord(SQLModel, table=True):
    """Per-user, per-day counter of processed messages.

    One row per (user_id, day). The subscription service upserts/increments it
    for every accepted user message and consults it before accepting new ones.
    """

    __tablename__ = "usage_record"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    day: date = Field(index=True)
    messages: int = Field(default=0)
    tool_calls: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
