"""Contacts message handler."""
import json

from app.services.whatsapp.handlers.base import BaseMessageHandler, HandlerResult
from app.services.whatsapp.parser import ParsedMessage
from app.services.conversation_service import ConversationContext


class ContactsHandler(BaseMessageHandler):
    """Pass shared contact cards through to the model as compact JSON."""

    async def handle(
        self,
        message: ParsedMessage,
        context: ConversationContext,
    ) -> HandlerResult:
        contacts = message.content.contacts or []
        try:
            payload = json.dumps(contacts, ensure_ascii=False)[:2000]
        except (TypeError, ValueError):
            payload = "<unparseable>"
        processed = (
            f"User shared {len(contacts)} contact card(s). "
            f"Raw data (truncated): {payload}. "
            "Confirm what they want you to do with these contacts."
        )
        return HandlerResult(processed_content=processed, requires_ai=True)
