"""Per-user third-party integration record (OAuth tokens, status, scope)."""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Integration(SQLModel, table=True):
    """One row per (user, provider). Tokens are stored signed by JWT_SECRET
    via ``app.web.crypto`` so a casual DB dump doesn't leak OAuth grants."""

    __tablename__ = "integration"
    __table_args__ = ({"sqlite_autoincrement": True},)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    provider: str = Field(index=True)  # google | github | slack | ...
    account_email: Optional[str] = None
    scope: Optional[str] = None

    # Stored encoded by app.web.crypto (signed string, not real KMS-grade).
    access_token_enc: Optional[str] = None
    refresh_token_enc: Optional[str] = None
    expires_at: Optional[datetime] = None

    status: str = Field(default="active")  # active | revoked | error

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
