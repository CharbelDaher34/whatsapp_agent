"""Text message handler."""
from app.services.whatsapp.handlers.base import BaseMessageHandler, HandlerResult
from app.services.whatsapp.parser import ParsedMessage
from app.services.conversation.flow_service import ConversationContext


class TextHandler(BaseMessageHandler):
    """Handler for text messages."""
    
    async def handle(
        self,
        message: ParsedMessage,
        context: ConversationContext
    ) -> HandlerResult:
        """Handle text message."""
        return HandlerResult(
            processed_content=message.content.text,
            requires_ai=True
        )

