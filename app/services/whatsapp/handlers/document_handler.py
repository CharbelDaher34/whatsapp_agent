"""Document message handler.

Pro/Max plans get text extraction; Free is told to upgrade.
PDF / plain-text extraction is best-effort and capped to keep token cost sane.
"""
from typing import Optional

from app.services.whatsapp.handlers.base import BaseMessageHandler, HandlerResult
from app.services.whatsapp.parser import ParsedMessage
from app.services.conversation.flow_service import ConversationContext
from app.services.whatsapp.media_handler import process_incoming_media
from app.core.plans import get_plan
from app.core.logging import logger


_MAX_DOC_CHARS = 8000


def _extract_text(data: bytes, mime_type: Optional[str]) -> Optional[str]:
    """Best-effort text extraction for common document types."""
    try:
        if not mime_type:
            return None
        if mime_type.startswith("text/"):
            return data.decode("utf-8", errors="replace")[:_MAX_DOC_CHARS]
        if mime_type == "application/pdf":
            try:
                from pypdf import PdfReader  # type: ignore
            except ImportError:
                return None
            from io import BytesIO
            reader = PdfReader(BytesIO(data))
            chunks = []
            for page in reader.pages[:10]:
                try:
                    chunks.append(page.extract_text() or "")
                except Exception:
                    continue
                if sum(len(c) for c in chunks) > _MAX_DOC_CHARS:
                    break
            text = "\n".join(chunks).strip()
            return text[:_MAX_DOC_CHARS] if text else None
    except Exception as e:
        logger.warning(f"Document extraction failed ({mime_type}): {e}")
    return None


class DocumentHandler(BaseMessageHandler):
    async def handle(
        self,
        message: ParsedMessage,
        context: ConversationContext,
    ) -> HandlerResult:
        plan = get_plan(context.user.subscription_tier)
        c = message.content
        filename = c.filename or "document"
        mime = c.mime_type or "unknown"

        if not plan.can_read_documents:
            return HandlerResult(
                processed_content=(
                    f"User sent a document ({filename}, {mime}) but their {plan.display_name} "
                    "plan doesn't support document analysis. Politely explain and offer to upgrade."
                ),
                requires_ai=True,
            )

        if not c.media_id:
            return HandlerResult(
                processed_content=f"User sent a document ({filename}) but no media id was provided.",
                requires_ai=True,
            )

        try:
            data, mime_type = await process_incoming_media(c.media_id)
            extracted = _extract_text(data, mime_type)
            if extracted:
                processed = (
                    f"User sent a document '{filename}' ({mime_type}). "
                    f"Extracted text (first {len(extracted)} chars):\n\n{extracted}\n\n"
                    "Use this content to answer or ask a follow-up question."
                )
            else:
                processed = (
                    f"User sent a document '{filename}' ({mime_type}, {len(data)} bytes). "
                    "I couldn't extract readable text from it. Ask the user what they'd like to do."
                )
            return HandlerResult(processed_content=processed, requires_ai=True)
        except Exception as e:
            logger.error(f"Document handler failed for {c.media_id}: {e}")
            return HandlerResult(
                processed_content=(
                    f"User sent a document '{filename}' but it failed to download. "
                    "Apologize briefly and ask them to try again."
                ),
                requires_ai=True,
            )
