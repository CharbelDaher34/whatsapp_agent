"""Run the agent for a single user turn.

Responsibilities:
- Build the per-user PydanticAI agent (plan-aware tools/model).
- Set the tool context (phone + user_id) so tools can look up
  user-specific resources (Redis image path, Memory rows, OAuth tokens).
- Pre-load the user's most relevant memories into the prompt so the model
  has long-range context even when sliding-window history has dropped it.
- Run the model with optional multimodal image input.
"""
from typing import List, Optional

from pydantic_ai import BinaryContent

from app.agents.whatsapp_agent import build_agent_for_user
from app.core.logging import logger
from app.core.plans import get_plan
from app.db.session import get_session
from app.models.conversation import Conversation
from app.models.user import User
from app.services.memory_service import recall, render_memories
from app.tools.context import (
    clear_current_phone,
    clear_current_user_id,
    set_current_phone,
    set_current_user_id,
)


async def generate_reply(
    user: User,
    conversation: Conversation,
    new_text: str,
    history: List[str],
    image_data: Optional[bytes] = None,
    media_type: Optional[str] = None,
    phone: Optional[str] = None,
) -> str:
    """Run the agent and return its text output."""
    history_text = ""
    try:
        if phone:
            set_current_phone(phone)
        if user.id is not None:
            set_current_user_id(user.id)

        agent = build_agent_for_user(user)
        plan = get_plan(user.subscription_tier)

        memory_block = await _build_memory_block(user.id, new_text)

        history_tail = history[-plan.history_depth:] if history else []
        history_text = "\n".join(history_tail)

        prompt_text_parts = []
        if memory_block:
            prompt_text_parts.append(f"Memory about this user:\n{memory_block}")
        if history_text:
            prompt_text_parts.append(f"Conversation history:\n{history_text}")
        prompt_text_parts.append(f"User: {new_text}")
        prompt_text = "\n\n".join(prompt_text_parts)

        if image_data:
            actual_media_type = media_type or "image/jpeg"
            logger.info(
                f"🖼️ Multimodal prompt: {len(image_data)} bytes ({actual_media_type})"
            )
            prompt = [
                prompt_text,
                BinaryContent(data=image_data, media_type=actual_media_type),
            ]
        else:
            prompt = prompt_text

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
        clear_current_user_id()


async def _build_memory_block(user_id: Optional[int], query: Optional[str]) -> str:
    """Return a compact bullet list of the user's relevant memories."""
    if not user_id:
        return ""
    try:
        async with get_session() as session:
            memories = await recall(session, user_id, query, limit=8)
        return render_memories(memories)
    except Exception as e:
        logger.warning(f"Memory load failed (non-fatal): {e}")
        return ""
