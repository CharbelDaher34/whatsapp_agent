"""Base message handler interface."""
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel
from app.services.whatsapp.parser import ParsedMessage
from app.services.conversation.flow_service import ConversationContext


class HandlerResult(BaseModel):
    """Result from message handler."""
    processed_content: str
    media_data: Optional[bytes] = None
    media_type: Optional[str] = None  # MIME type of the media (e.g., image/png)
    requires_ai: bool = True  # Whether this message needs AI processing


class BaseMessageHandler(ABC):
    """Base class for message type handlers."""
    
    @abstractmethod
    async def handle(
        self,
        message: ParsedMessage,
        context: ConversationContext
    ) -> HandlerResult:
        """
        Handle a message of specific type.
        
        Args:
            message: Parsed message
            context: Conversation context
            
        Returns:
            HandlerResult with processed data
        """
        pass

