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
    
    # Log available tools for debugging
    tool_names = [t.name for t in tools]
    logger.info(f"🔧 Building agent for user (tier: {user.subscription_tier})")
    logger.info(f"🔧 Available tools: {tool_names}")
    
    if not pydantic_tools:
        logger.warning("⚠️  No tools available for this user!")
    
    # Build system prompt based on available tools
    base_prompt = (
        "You are a smart, friendly, and helpful WhatsApp assistant. "
        "Keep messages concise and WhatsApp-friendly (avoid very long responses unless necessary). "
        "Use emojis naturally to make the conversation lively. "
        "\n\n"
        "IMPORTANT - IMAGE HANDLING:\n"
        "- When a user sends you an image, you CAN SEE IT directly. Describe what you see!\n"
        "- DO NOT say 'there was an error' or 'please resend' - you can view images.\n"
        "- Only use tools if the user EXPLICITLY asks to CREATE or MODIFY an image.\n"
    )
    
    if tool_names:
        tool_instructions = (
            "\n\n"
            "IMPORTANT TOOL USAGE RULES:\n"
            "- You have access to the following tools: " + ", ".join(tool_names) + "\n"
        )
        
        if "text_to_image" in tool_names:
            tool_instructions += (
                "- You MUST use the text_to_image tool when the user asks for an image, picture, or photo.\n"
                "- NEVER say you will create an image without actually calling the tool.\n"
                "- NEVER make up file paths or URLs - always call the tool to generate the actual image.\n"
                "- When the tool returns IMAGE_URL:path, return it exactly as is.\n"
            )
        
        if "image_to_image" in tool_names:
            tool_instructions += (
                "- Use the image_to_image tool ONLY when the user explicitly asks to MODIFY, TRANSFORM, or EDIT an image.\n"
                "- DO NOT use this tool just to view or analyze an image. You can see images directly.\n"
                "- When calling image_to_image, include BOTH the [USER_IMAGE_PATH:...] tag AND your transformation instruction.\n"
                "- Example: Call image_to_image with 'make it cartoon style [USER_IMAGE_PATH:images/incoming_xxx.jpg]'\n"
            )
        
        system_prompt = base_prompt + tool_instructions
    else:
        system_prompt = base_prompt + (
            "\n\n"
            "Note: You currently don't have access to tools like image generation. "
            "If the user asks for images or advanced features, politely explain that "
            "this feature is not available on their current plan."
        )
    
    # Create OpenAI provider with API key, then create model
    # Reference: https://ai.pydantic.dev/models/openai/
    provider = OpenAIProvider(api_key=settings.OPENAI_API_KEY)
    model = OpenAIChatModel("gpt-4o", provider=provider)
    
    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        tools=pydantic_tools,
    )
    
    return agent


