"""AI router service for generating AI responses."""
from app.models.user import User
from app.models.conversation import Conversation
from app.agents.whatsapp_agent import build_agent_for_user
from typing import List, Optional
from app.core.logging import logger
from pydantic_ai.messages import BinaryContent


async def generate_reply(
    user: User,
    conversation: Conversation,
    new_text: str,
    history: List[str],
    image_data: Optional[bytes] = None
) -> str:
    """
    Generate an AI reply for the user's message.
    Builds an agent with the user's available tools and processes the message.
    Supports image input via binary data.
    """
    try:
        agent = build_agent_for_user(user)
        
        # Build context from conversation history
        history_text = "Conversation history:\n" + "\n".join(history[-10:]) if history else ""
        
        if image_data:
            # Multi-modal prompt with image using pydantic-ai BinaryContent
            prompt = [
                f"{history_text}\n\nUser: {new_text}",
                BinaryContent(data=image_data, media_type='image/jpeg')
            ]
        else:
            # Text-only prompt
            prompt = f"{history_text}\n\nUser: {new_text}"
        
        result = await agent.run(prompt)
        return str(result.output)
    except Exception as e:
        logger.error(f"Error generating reply: {e}")
        # Fallback if agent.run fails with multimodal
        if image_data:
             logger.warning("Retrying with text-only prompt due to error")
             try:
                 prompt = f"{history_text}\n\nUser: [Image sent] {new_text}"
                 result = await agent.run(prompt)
                 return str(result.output)
             except Exception as ex:
                 logger.error(f"Retry failed: {ex}")
        
        return "I'm sorry, I encountered an error processing your message. Please try again."




