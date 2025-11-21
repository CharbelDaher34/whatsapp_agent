"""Tool configuration model."""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class ToolConfig(SQLModel, table=True):
    """Tool configuration for admin control."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    enabled: bool = Field(default=True)
    min_tier: str = Field(default="free")  # free, plus, pro
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


