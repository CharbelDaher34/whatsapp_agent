"""WhatsApp agent with PydanticAI integration."""
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from typing import List
from app.models.user import User
from app.tools.registry import get_tools_for_user
from app.core.config import settings
from app.core.logging import logger


def build_agent_for_user(user: User) -> Agent:
    """
    Build a PydanticAI agent customized for a specific user.
    The agent has access only to tools available for the user's subscription tier.
    """
    if not settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not set in .env file!")
        raise ValueError("OPENAI_API_KEY must be set in environment variables")
    
    tools = get_tools_for_user(user)
    pydantic_tools = [t.to_pydanticai_tool() for t in tools]
    
    system_prompt = (
        "You are a helpful WhatsApp assistant. "
        "Keep messages concise and WhatsApp-friendly (avoid very long responses). "
        "You have access to tools; only use them when truly needed. "
        "Be conversational and friendly."
    )
    
    # Create OpenAI provider with API key, then create model
    # Reference: https://ai.pydantic.dev/models/openai/
    provider = OpenAIProvider(api_key=settings.OPENAI_API_KEY)
    model = OpenAIChatModel("gpt-4o-mini", provider=provider)
    
    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        tools=pydantic_tools,
    )
    
    return agent


