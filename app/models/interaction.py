"""Interaction model for tracking button/list selections."""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class Interaction(SQLModel, table=True):
    """Track user interactions with buttons and lists."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    conversation_id: int = Field(foreign_key="conversation.id")
    
    interaction_type: str  # "button" or "list"
    interaction_id: str  # Button ID or list item ID
    interaction_title: str  # Button title or list item title
    
    message_id: Optional[str] = None  # Original WhatsApp message ID
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

