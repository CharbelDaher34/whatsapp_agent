"""Broadcast message model."""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class Broadcast(SQLModel, table=True):
    """Broadcast message tracking."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Broadcast details
    message: str
    target_tier: Optional[str] = None  # None = all, "free", "plus", "pro"
    target_status: str = "active"  # "active", "all"
    
    # Media
    media_type: Optional[str] = None  # "image", "document", etc.
    media_url: Optional[str] = None
    
    # Stats
    total_recipients: int = 0
    sent_count: int = 0
    failed_count: int = 0
    
    # Status
    status: str = "pending"  # "pending", "in_progress", "completed", "failed"
    
    # Timestamps
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "admin"  # Admin user identifier

