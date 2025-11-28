"""Audio message handler."""
from app.services.whatsapp.handlers.base import BaseMessageHandler, HandlerResult
from app.services.whatsapp.parser import ParsedMessage
from app.services.conversation.flow_service import ConversationContext
from app.core.logging import logger


class AudioHandler(BaseMessageHandler):
    """Handler for audio messages."""
    
    async def handle(
        self,
        message: ParsedMessage,
        context: ConversationContext
    ) -> HandlerResult:
        """Handle audio message."""
        # Could add audio transcription later
        logger.info(f"User sent audio: {message.content.media_id}")
        
        return HandlerResult(
            processed_content="[Audio message received]",
            requires_ai=True
        )

