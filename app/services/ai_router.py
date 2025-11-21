"""AI router service for generating AI responses."""
from app.models.user import User
from app.models.conversation import Conversation
from app.agents.whatsapp_agent import build_agent_for_user
from typing import List
from app.core.logging import logger


async def generate_reply(
    user: User,
    conversation: Conversation,
    new_text: str,
    history: List[str]
) -> str:
    """
    Generate an AI reply for the user's message.
    Builds an agent with the user's available tools and processes the message.
    """
    try:
        agent = build_agent_for_user(user)
        
        # Build context from conversation history
        prompt = (
            "Conversation history:\n" +
            "\n".join(history[-10:]) +  # last 10 messages
            f"\n\nUser: {new_text}"
        )
        
        result = await agent.run(prompt)
        return str(result.output)
    except Exception as e:
        logger.error(f"Error generating reply: {e}")
        return "I'm sorry, I encountered an error processing your message. Please try again."


