"""Location message handler."""
from app.services.whatsapp.handlers.base import BaseMessageHandler, HandlerResult
from app.services.whatsapp.parser import ParsedMessage
from app.services.conversation_service import ConversationContext


class LocationHandler(BaseMessageHandler):
    """Surface lat/long and any label so the assistant can reason about it."""

    async def handle(
        self,
        message: ParsedMessage,
        context: ConversationContext,
    ) -> HandlerResult:
        c = message.content
        parts = []
        if c.location_name:
            parts.append(f"name={c.location_name!r}")
        if c.location_address:
            parts.append(f"address={c.location_address!r}")
        if c.latitude is not None and c.longitude is not None:
            parts.append(f"coords=({c.latitude:.6f}, {c.longitude:.6f})")
        meta = ", ".join(parts) or "no metadata"
        processed = f"User shared a location ({meta}). Acknowledge it and ask what they want to do."
        return HandlerResult(processed_content=processed, requires_ai=True)
