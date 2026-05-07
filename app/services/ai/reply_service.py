"""AI reply generation + tool-output post-processing."""
from typing import List, Optional

from pydantic import BaseModel

from app.core.exceptions import AIGenerationError
from app.core.logging import logger
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services.ai_router import generate_reply as generate_ai_reply
from app.services.whatsapp.media_handler import extract_image_url_from_text


_NO_REPLY_SENTINEL = "[NO_TEXT_REPLY]"


class ProcessedReply(BaseModel):
    """Final, ready-to-send representation of the assistant's response."""

    content: str
    reply_type: str  # text | image | none
    media_path: Optional[str] = None
    caption: Optional[str] = None


async def generate_reply_for_user(
    user: User,
    conversation: Conversation,
    message_content: str,
    history: List[Message],
    image_data: Optional[bytes] = None,
    media_type: Optional[str] = None,
    phone: Optional[str] = None,
) -> str:
    """Generate the raw model reply for the user's most recent message."""
    try:
        history_list = [f"{msg.sender}: {msg.content}" for msg in history]
        if image_data:
            logger.info(
                f"📸 Passing image to AI ({len(image_data)} bytes, {media_type or 'unknown'})"
            )
        return await generate_ai_reply(
            user=user,
            conversation=conversation,
            new_text=message_content,
            history=history_list,
            image_data=image_data,
            media_type=media_type,
            phone=phone,
        )
    except Exception as e:
        logger.error(f"AI generation failed: {e}", exc_info=True)
        raise AIGenerationError(f"Failed to generate reply: {e}")


async def process_tool_outputs(reply_text: str) -> ProcessedReply:
    """Convert the raw model output into a typed reply.

    Recognises three patterns produced by tools:
      * ``IMAGE_URL:<path>`` (with optional caption before it) — send image
      * ``[NO_TEXT_REPLY]`` — agent already pushed an interactive message; skip text
      * anything else — plain text
    """
    text = (reply_text or "").strip()

    # Tool already sent an interactive message; don't double-message.
    if _NO_REPLY_SENTINEL in text:
        cleaned = text.replace(_NO_REPLY_SENTINEL, "").strip()
        if not cleaned:
            return ProcessedReply(content="", reply_type="none")
        # Some models leave both an interactive call AND a short text — keep the text.
        return ProcessedReply(content=cleaned, reply_type="text")

    caption, image_path = extract_image_url_from_text(text)
    if image_path:
        logger.info(f"🖼️ Tool output: image at {image_path}")
        return ProcessedReply(
            content=caption or "Here's the image you requested!",
            reply_type="image",
            media_path=image_path,
            caption=caption,
        )

    if not text:
        return ProcessedReply(content="", reply_type="none")

    return ProcessedReply(content=text, reply_type="text")
