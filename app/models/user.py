"""User model."""
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.conversation import Conversation


# Canonical subscription tiers. Keep in sync with app.core.plans.PLANS.
SUBSCRIPTION_TIERS = ("free", "pro", "max")


class User(SQLModel, table=True):
    """A WhatsApp user."""

    id: Optional[int] = Field(default=None, primary_key=True)
    phone: str = Field(index=True, unique=True)
    display_name: Optional[str] = None

    subscription_tier: str = Field(default="free")  # free | pro | max
    is_active: bool = Field(default=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    conversations: List["Conversation"] = Relationship(back_populates="user")
