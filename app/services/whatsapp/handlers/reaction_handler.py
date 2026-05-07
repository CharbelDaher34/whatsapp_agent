"""Reaction (emoji on a previous message) handler."""
from app.services.whatsapp.handlers.base import BaseMessageHandler, HandlerResult
from app.services.whatsapp.parser import ParsedMessage
from app.services.conversation.flow_service import ConversationContext


class ReactionHandler(BaseMessageHandler):
    """Reactions don't need an AI reply by default — they're acknowledgements."""

    async def handle(
        self,
        message: ParsedMessage,
        context: ConversationContext,
    ) -> HandlerResult:
        emoji = message.content.reaction_emoji or ""
        # Empty emoji means the user removed a reaction.
        if not emoji:
            processed = "User removed a reaction."
        else:
            processed = f"User reacted with {emoji}."
        return HandlerResult(
            processed_content=processed,
            # Don't pester the user with a reply just because they added an emoji.
            requires_ai=False,
        )
