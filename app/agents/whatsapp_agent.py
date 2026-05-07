"""Build the per-user PydanticAI agent for the WhatsApp assistant.

The agent is deliberately *plan-aware*: tool access, model choice and the
system prompt all reflect the user's subscription tier.

It can also drive the conversation back to the user — see the ``ask_buttons``
and ``ask_list`` tools — by sending interactive WhatsApp messages directly
and signalling the response builder to skip the text reply.
"""
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.models.user import User
from app.tools.registry import get_tools_for_user
from app.core.config import settings
from app.core.plans import get_plan
from app.core.logging import logger


_NO_REPLY_SENTINEL = "[NO_TEXT_REPLY]"


def _build_system_prompt(user: User, tool_names: list[str]) -> str:
    plan = get_plan(user.subscription_tier)
    daily = "unlimited" if plan.messages_per_day == -1 else f"{plan.messages_per_day}/day"
    monthly = "unlimited" if plan.messages_per_month == -1 else f"{plan.messages_per_month}/month"

    sections: list[str] = [
        "You are a smart, friendly, production-grade WhatsApp assistant.",
        "Keep replies short and WhatsApp-friendly. Use emojis sparingly.",
        "Be proactive: when the user's intent is unclear OR you need a missing detail "
        "to complete a task, ASK a follow-up question instead of guessing.",
        "Prefer a structured question over free text when there are 2-10 obvious choices "
        "(use the `ask_buttons` tool for ≤3 choices, `ask_list` tool for 4-10).",
        "",
        f"Current user plan: **{plan.display_name}**.",
        f"Quota: {daily}, {monthly}.",
    ]

    capability_lines: list[str] = []
    if plan.can_generate_images:
        capability_lines.append("- can generate images from text (`text_to_image`)")
    else:
        capability_lines.append("- CANNOT generate images on this plan; offer to upgrade.")
    if plan.can_transform_images:
        capability_lines.append("- can transform/edit images the user uploaded (`image_to_image`)")
    else:
        capability_lines.append("- CANNOT edit images on this plan; offer to upgrade.")
    if plan.can_transcribe_audio:
        capability_lines.append("- can transcribe voice notes the user sends")
    else:
        capability_lines.append("- CANNOT transcribe voice notes on this plan; ask user to type instead.")
    if plan.can_read_documents:
        capability_lines.append("- can read uploaded text/PDF documents")
    else:
        capability_lines.append("- CANNOT analyse documents on this plan.")

    sections.append("Capabilities on this plan:")
    sections.extend(capability_lines)

    sections.extend([
        "",
        "Vision: when a user sends an image, you receive it directly — describe what "
        "you see; do NOT claim 'I can't view images'. Only call `image_to_image` if "
        "the user explicitly asks to MODIFY the image.",
        "",
        f"Available tools: {', '.join(tool_names) if tool_names else 'none'}.",
    ])

    if "ask_buttons" in tool_names or "ask_list" in tool_names:
        sections.extend([
            "",
            "Asking the user for input:",
            "- Pass JSON to ask_buttons: {\"prompt\":\"...\",\"options\":[\"A\",\"B\",\"C\"]}",
            "- Pass JSON to ask_list: {\"prompt\":\"...\",\"button\":\"Choose\","
            "\"items\":[{\"id\":\"x\",\"title\":\"X\",\"description\":\"...\"}]}",
            f"- After calling either tool, end your reply with exactly {_NO_REPLY_SENTINEL} "
            "so the user only sees the interactive message.",
        ])

    if "text_to_image" in tool_names:
        sections.extend([
            "",
            "Image generation: only call `text_to_image` when the user clearly asks for "
            "a new image. Pass the prompt as plain text. Return the tool output verbatim "
            "if it begins with IMAGE_URL: — the response builder handles the rest.",
        ])

    if "image_to_image" in tool_names:
        sections.extend([
            "",
            "Image editing: only call `image_to_image` when the user wants to modify their "
            "most recent image. Pass the transformation instruction as plain text — the "
            "tool already knows which image to use.",
        ])

    if "remember" in tool_names or "recall" in tool_names:
        sections.extend([
            "",
            "Memory:",
            "- The 'Memory about this user' block in the prompt is your long-term recall — "
            "use it before asking the user something they've already told you.",
            "- Call `remember` ONLY for stable facts (name, location, timezone, preferences, "
            "ongoing projects). Skip transient or sensitive details (passwords, financial info).",
            "- Call `recall` to search memory by topic; call `forget` to drop a memory.",
        ])

    if "gmail_search" in tool_names:
        sections.extend([
            "",
            "Gmail: call `gmail_search` only when the user asks something that requires "
            "their email (recent invoices, messages from someone, etc.). If the tool says "
            "Gmail isn't connected, ask them to connect it from the dashboard.",
        ])

    sections.extend([
        "",
        "Refusal etiquette: if a request is outside this plan, briefly explain the limit "
        "and suggest an upgrade. Never bypass plan rules.",
    ])

    return "\n".join(sections)


def build_agent_for_user(user: User) -> Agent:
    """Construct a PydanticAI Agent customized for the user's plan."""
    if not settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not set!")
        raise ValueError("OPENAI_API_KEY must be set in environment variables")

    plan = get_plan(user.subscription_tier)
    tools = get_tools_for_user(user)
    pydantic_tools = [t.to_pydanticai_tool() for t in tools]
    tool_names = [t.name for t in tools]

    logger.info(
        f"🔧 Building agent for {user.phone or '?'} (plan={plan.name}, "
        f"model={plan.model}, tools={tool_names})"
    )

    system_prompt = _build_system_prompt(user, tool_names)

    provider = OpenAIProvider(api_key=settings.OPENAI_API_KEY)
    model = OpenAIChatModel(plan.model, provider=provider)

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=pydantic_tools,
    )
