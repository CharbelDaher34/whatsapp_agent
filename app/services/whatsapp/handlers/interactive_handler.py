"""Interactive message handler (buttons, lists)."""
from app.services.whatsapp.handlers.base import BaseMessageHandler, HandlerResult
from app.services.whatsapp.parser import ParsedMessage
from app.services.conversation.flow_service import ConversationContext
from app.core.logging import logger


class InteractiveHandler(BaseMessageHandler):
    """Handler for interactive messages (button clicks, list selections)."""
    
    async def handle(
        self,
        message: ParsedMessage,
        context: ConversationContext
    ) -> HandlerResult:
        """Handle interactive message."""
        content = message.content
        
        if content.button_id:
            logger.info(f"Button clicked: {content.button_title} ({content.button_id})")
            processed = f"[Button: {content.button_title}]"
        elif content.list_id:
            logger.info(f"List selected: {content.list_title} ({content.list_id})")
            processed = f"[List: {content.list_title}]"
        else:
            processed = message.content.text
        
        return HandlerResult(
            processed_content=processed,
            requires_ai=True
        )

