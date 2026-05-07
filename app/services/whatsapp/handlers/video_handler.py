"""Video message handler.

We don't run vision over full videos (cost + WhatsApp limits). The handler
acknowledges the video, surfaces caption + size info, and lets the AI ask
follow-up questions.
"""
from app.services.whatsapp.handlers.base import BaseMessageHandler, HandlerResult
from app.services.whatsapp.parser import ParsedMessage
from app.services.conversation_service import ConversationContext
from app.core.logging import logger


class VideoHandler(BaseMessageHandler):
    async def handle(
        self,
        message: ParsedMessage,
        context: ConversationContext,
    ) -> HandlerResult:
        c = message.content
        caption = c.caption or ""
        logger.info(f"User sent video: {c.media_id} (mime={c.mime_type})")
        if caption:
            processed = (
                f"User sent a video with caption: {caption!r}. "
                "Respond to the caption naturally; mention you can't watch the video itself."
            )
        else:
            processed = (
                "User sent a video without a caption. Acknowledge it warmly and "
                "ask what they'd like you to help with — you can't watch the video itself."
            )
        return HandlerResult(processed_content=processed, requires_ai=True)
