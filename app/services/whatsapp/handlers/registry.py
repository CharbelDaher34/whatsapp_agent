"""Message handler registry — one handler per WhatsApp inbound type."""
from app.services.whatsapp.parser import MessageType, ParsedMessage
from app.services.conversation.flow_service import ConversationContext
from app.services.whatsapp.handlers.base import BaseMessageHandler, HandlerResult
from app.services.whatsapp.handlers.text_handler import TextHandler
from app.services.whatsapp.handlers.image_handler import ImageHandler
from app.services.whatsapp.handlers.video_handler import VideoHandler
from app.services.whatsapp.handlers.audio_handler import AudioHandler
from app.services.whatsapp.handlers.interactive_handler import InteractiveHandler
from app.services.whatsapp.handlers.location_handler import LocationHandler
from app.services.whatsapp.handlers.contacts_handler import ContactsHandler
from app.services.whatsapp.handlers.sticker_handler import StickerHandler
from app.services.whatsapp.handlers.reaction_handler import ReactionHandler
from app.services.whatsapp.handlers.document_handler import DocumentHandler
from app.core.logging import logger


class DefaultHandler(BaseMessageHandler):
    """Fallback for unknown / unsupported types."""

    async def handle(
        self,
        message: ParsedMessage,
        context: ConversationContext,
    ) -> HandlerResult:
        logger.info(f"Falling back to default handler for type={message.message_type}")
        return HandlerResult(
            processed_content=(
                f"User sent an unsupported message type ({message.message_type.value}). "
                "Politely tell them what kinds of messages you support."
            ),
            requires_ai=True,
        )


HANDLERS = {
    MessageType.TEXT: TextHandler(),
    MessageType.IMAGE: ImageHandler(),
    MessageType.VIDEO: VideoHandler(),
    MessageType.AUDIO: AudioHandler(),
    MessageType.VOICE: AudioHandler(),
    MessageType.DOCUMENT: DocumentHandler(),
    MessageType.STICKER: StickerHandler(),
    MessageType.REACTION: ReactionHandler(),
    MessageType.LOCATION: LocationHandler(),
    MessageType.CONTACTS: ContactsHandler(),
    MessageType.INTERACTIVE: InteractiveHandler(),
    MessageType.BUTTON: InteractiveHandler(),
}


async def handle_message(
    message: ParsedMessage,
    context: ConversationContext,
) -> HandlerResult:
    """Dispatch a parsed message to its type-specific handler."""
    handler = HANDLERS.get(message.message_type, DefaultHandler())
    return await handler.handle(message, context)
