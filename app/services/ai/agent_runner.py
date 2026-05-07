"""AI reply generation routing.

Builds the agent for the user, sets the per-call phone context (so tools can
look up Redis state for that user), and runs the model with optional
multimodal image input.
"""
from typing import List, Optional

from pydantic_ai import BinaryContent

from app.agents.whatsapp_agent import build_agent_for_user
from app.core.logging import logger
from app.core.plans import get_plan
from app.models.conversation import Conversation
from app.models.user import User
from app.tools.context import clear_current_phone, set_current_phone


async def generate_reply(
    user: User,
    conversation: Conversation,
    new_text: str,
    history: List[str],
    image_data: Optional[bytes] = None,
    media_type: Optional[str] = None,
    phone: Optional[str] = None,
) -> str:
    """Run the agent and return its text output. Falls back to a plain prompt
    on multimodal failure to avoid losing the conversation."""
    try:
        if phone:
            set_current_phone(phone)

        agent = build_agent_for_user(user)
        plan = get_plan(user.subscription_tier)

        # Trim history to plan depth.
        history_tail = history[-plan.history_depth:] if history else []
        history_text = "Conversation history:\n" + "\n".join(history_tail) if history_tail else ""

        if image_data:
            actual_media_type = media_type or "image/jpeg"
            logger.info(
                f"🖼️ Multimodal prompt: {len(image_data)} bytes ({actual_media_type})"
            )
            prompt = [
                f"{history_text}\n\nUser: {new_text}",
                BinaryContent(data=image_data, media_type=actual_media_type),
            ]
        else:
            prompt = f"{history_text}\n\nUser: {new_text}"

        result = await agent.run(prompt)
        output = str(result.output or "").strip()
        logger.info(f"✅ AI reply generated ({len(output)} chars)")
        return output
    except Exception as e:
        logger.error(f"❌ Error generating reply: {e}", exc_info=True)
        if image_data:
            try:
                logger.warning("⚠️ Retrying with text-only prompt")
                fallback = f"{history_text}\n\nUser: [Image sent] {new_text}"
                result = await agent.run(fallback)
                return str(result.output or "")
            except Exception as ex:
                logger.error(f"❌ Retry failed: {ex}", exc_info=True)
        return (
            "Sorry, I had trouble processing that. Could you try again or rephrase your request?"
        )
    finally:
        clear_current_phone()
