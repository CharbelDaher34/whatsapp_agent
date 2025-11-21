"""Message model."""
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Message(SQLModel, table=True):
    """Message model for storing conversation messages."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id")
    sender: str  # "user" or "bot"
    msg_type: str = Field(default="text")  # text, image, document, etc.
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    conversation: "Conversation" = Relationship(back_populates="messages")


