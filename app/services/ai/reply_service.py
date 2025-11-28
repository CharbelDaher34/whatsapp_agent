"""AI reply generation service."""
from typing import Optional, List
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.ai_router import generate_reply as generate_ai_reply
from app.services.whatsapp.media_handler import extract_image_url_from_text
from app.core.logging import logger
from app.core.exceptions import AIGenerationError


class ProcessedReply(BaseModel):
    """Processed AI reply with tool outputs."""
    content: str
    reply_type: str  # text, image
    media_path: Optional[str] = None
    caption: Optional[str] = None


async def generate_reply_for_user(
    user: User,
    conversation: Conversation,
    message_content: str,
    history: List[Message],
    image_data: Optional[bytes] = None,
    media_type: Optional[str] = None,
    phone: Optional[str] = None
) -> str:
    """
    Generate AI reply for a user message.
    
    Args:
        user: User object
        conversation: Conversation object
        message_content: User's message content
        history: Conversation history
        image_data: Optional image binary data if user sent image
        media_type: Optional MIME type of the media (e.g., image/png)
        phone: User's phone number for tool context
        
    Returns:
        AI-generated reply text
        
    Raises:
        AIGenerationError: If generation fails
    """
    try:
        # Convert history to format expected by generate_reply (List[str])
        history_list = [
            f"{msg.sender}: {msg.content}"
            for msg in history
        ]
        
        if image_data:
            logger.info(f"📸 Passing image to AI ({len(image_data)} bytes, {media_type or 'unknown type'})")
        
        # Generate reply using existing AI router
        reply = await generate_ai_reply(
            user=user,
            conversation=conversation,
            new_text=message_content,
            history=history_list,
            image_data=image_data,
            media_type=media_type,
            phone=phone
        )
        
        logger.debug(f"Generated AI reply ({len(reply)} chars)")
        return reply
        
    except Exception as e:
        logger.error(f"AI generation failed: {e}")
        raise AIGenerationError(f"Failed to generate reply: {e}")


async def process_tool_outputs(reply_text: str) -> ProcessedReply:
    """
    Process AI reply to extract tool outputs (e.g., generated images).
    
    Args:
        reply_text: Raw AI reply text
        
    Returns:
        ProcessedReply with extracted tool outputs
    """
    # Check for image generation output
    caption, image_path = extract_image_url_from_text(reply_text)
    
    if image_path:
        logger.info(f"Tool output detected: image at {image_path}")
        return ProcessedReply(
            content=caption or "Here's the image you requested!",
            reply_type="image",
            media_path=image_path,
            caption=caption
        )
    
    # Plain text response
    return ProcessedReply(
        content=reply_text,
        reply_type="text"
    )

