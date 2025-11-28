"""Message handler registry."""
from app.services.whatsapp.parser import MessageType, ParsedMessage
from app.services.conversation.flow_service import ConversationContext
from app.services.whatsapp.handlers.base import BaseMessageHandler, HandlerResult
from app.services.whatsapp.handlers.text_handler import TextHandler
from app.services.whatsapp.handlers.image_handler import ImageHandler
from app.services.whatsapp.handlers.video_handler import VideoHandler
from app.services.whatsapp.handlers.audio_handler import AudioHandler
from app.services.whatsapp.handlers.interactive_handler import InteractiveHandler
from app.core.logging import logger


class DefaultHandler(BaseMessageHandler):
    """Default handler for unsupported message types."""
    
    async def handle(
        self,
        message: ParsedMessage,
        context: ConversationContext
    ) -> HandlerResult:
        """Handle unsupported message type."""
        logger.warning(f"Unsupported message type: {message.message_type}")
        return HandlerResult(
            processed_content=f"[{message.message_type.value} message not fully supported yet]",
            requires_ai=True
        )


# Registry of message type handlers
HANDLERS = {
    MessageType.TEXT: TextHandler(),
    MessageType.IMAGE: ImageHandler(),
    MessageType.VIDEO: VideoHandler(),
    MessageType.AUDIO: AudioHandler(),
    MessageType.INTERACTIVE: InteractiveHandler(),
}


async def handle_message(
    message: ParsedMessage,
    context: ConversationContext
) -> HandlerResult:
    """
    Route message to appropriate handler based on type.
    
    Args:
        message: Parsed message
        context: Conversation context
        
    Returns:
        HandlerResult from appropriate handler
    """
    handler = HANDLERS.get(message.message_type, DefaultHandler())
    return await handler.handle(message, context)

