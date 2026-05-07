"""Sticker message handler."""
from app.services.whatsapp.handlers.base import BaseMessageHandler, HandlerResult
from app.services.whatsapp.parser import ParsedMessage
from app.services.conversation.flow_service import ConversationContext


class StickerHandler(BaseMessageHandler):
    """Acknowledge stickers without trying to download/render them."""

    async def handle(
        self,
        message: ParsedMessage,
        context: ConversationContext,
    ) -> HandlerResult:
        kind = "animated sticker" if message.content.animated else "sticker"
        return HandlerResult(
            processed_content=f"User sent a {kind}. Reply playfully and ask what they need.",
            requires_ai=True,
        )
