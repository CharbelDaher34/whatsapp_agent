"""Video message handler."""
from app.services.whatsapp.handlers.base import BaseMessageHandler, HandlerResult
from app.services.whatsapp.parser import ParsedMessage
from app.services.conversation.flow_service import ConversationContext
from app.core.logging import logger


class VideoHandler(BaseMessageHandler):
    """Handler for video messages."""
    
    async def handle(
        self,
        message: ParsedMessage,
        context: ConversationContext
    ) -> HandlerResult:
        """Handle video message."""
        # For now, acknowledge video without downloading
        # Could add video processing later
        content = message.content.caption or "[Video received]"
        logger.info(f"User sent video: {message.content.media_id}")
        
        return HandlerResult(
            processed_content=content,
            requires_ai=True
        )

