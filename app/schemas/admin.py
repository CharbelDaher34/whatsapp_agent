"""Admin API schemas."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserResponse(BaseModel):
    """User response schema."""
    id: int
    phone: str
    display_name: Optional[str]
    subscription_tier: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UpdateSubscriptionRequest(BaseModel):
    """Update subscription request."""
    tier: str


class UpdateToolRequest(BaseModel):
    """Update tool configuration request."""
    enabled: bool
    min_tier: str = "free"


class ToolResponse(BaseModel):
    """Tool configuration response."""
    id: int
    name: str
    enabled: bool
    min_tier: str
    created_at: datetime
    updated_at: datetime


