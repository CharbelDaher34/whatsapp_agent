"""AI router service for generating AI responses."""
from app.models.user import User
from app.models.conversation import Conversation
from app.agents.whatsapp_agent import build_agent_for_user
from app.tools.context import set_current_phone, clear_current_phone
from typing import List, Optional
from app.core.logging import logger
from pydantic_ai import BinaryContent


async def generate_reply(
    user: User,
    conversation: Conversation,
    new_text: str,
    history: List[str],
    image_data: Optional[bytes] = None,
    media_type: Optional[str] = None,
    phone: Optional[str] = None
) -> str:
    """
    Generate an AI reply for the user's message.
    Builds an agent with the user's available tools and processes the message.
    Supports image input via binary data.
    """
    try:
        # Set phone in context so tools can access it
        if phone:
            set_current_phone(phone)
            logger.debug(f"Set phone context: {phone}")
        
        agent = build_agent_for_user(user)
        
        # Build context from conversation history
        history_text = "Conversation history:\n" + "\n".join(history[-10:]) if history else ""
        
        if image_data:
            # Use provided media_type or default to image/jpeg
            actual_media_type = media_type or 'image/jpeg'
            logger.info(f"🖼️ Processing message with image ({len(image_data)} bytes, {actual_media_type})")
            
            # Verify image data is valid by checking first few bytes (magic numbers)
            if len(image_data) > 4:
                magic = image_data[:4].hex()
                logger.debug(f"Image magic bytes: {magic}")
            
            # Multi-modal prompt with image using pydantic-ai BinaryContent
            prompt = [
                f"{history_text}\n\nUser: {new_text}",
                BinaryContent(data=image_data, media_type=actual_media_type)
            ]
            logger.debug(f"Prompt structure: text + BinaryContent({actual_media_type})")
        else:
            logger.debug("Processing text-only message")
            # Text-only prompt
            prompt = f"{history_text}\n\nUser: {new_text}"
        
        logger.debug("Calling agent.run()...")
        result = await agent.run(prompt)
        logger.info(f"✅ AI reply generated: {result.output[:100]}...")
        logger.debug(f"Full response: {result.output}")
        return str(result.output)
    except Exception as e:
        logger.error(f"❌ Error generating reply: {e}", exc_info=True)
        # Fallback if agent.run fails with multimodal
        if image_data:
             logger.warning("⚠️ Retrying with text-only prompt due to error")
             try:
                 prompt = f"{history_text}\n\nUser: [Image sent] {new_text}"
                 result = await agent.run(prompt)
                 return str(result.output)
             except Exception as ex:
                 logger.error(f"❌ Retry failed: {ex}", exc_info=True)
        
        return "I'm sorry, I encountered an error processing your message. Please try again."
    finally:
        # Clear context after processing
        clear_current_phone()




