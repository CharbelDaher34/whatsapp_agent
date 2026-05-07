"""Audio / voice-note message handler with tier-gated transcription."""
from typing import Optional

from app.services.whatsapp.handlers.base import BaseMessageHandler, HandlerResult
from app.services.whatsapp.parser import ParsedMessage
from app.services.conversation.flow_service import ConversationContext
from app.services.whatsapp.media_handler import process_incoming_media
from app.core.plans import get_plan
from app.core.config import settings
from app.core.logging import logger


async def _transcribe(data: bytes, mime_type: Optional[str]) -> Optional[str]:
    """Transcribe audio with OpenAI Whisper. Returns None on any failure."""
    if not settings.OPENAI_API_KEY:
        return None
    try:
        from openai import AsyncOpenAI  # type: ignore
    except ImportError:
        return None
    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        # OpenAI SDK accepts a (filename, bytes, mime) tuple for the file param.
        ext = "ogg"
        if mime_type:
            if "mpeg" in mime_type:
                ext = "mp3"
            elif "mp4" in mime_type or "m4a" in mime_type:
                ext = "m4a"
            elif "wav" in mime_type:
                ext = "wav"
        file_tuple = (f"audio.{ext}", data, mime_type or "audio/ogg")
        result = await client.audio.transcriptions.create(
            model="whisper-1",
            file=file_tuple,
        )
        return (result.text or "").strip() or None
    except Exception as e:
        logger.warning(f"Whisper transcription failed: {e}")
        return None


class AudioHandler(BaseMessageHandler):
    """Handle audio messages, transcribing for Pro/Max plans."""

    async def handle(
        self,
        message: ParsedMessage,
        context: ConversationContext,
    ) -> HandlerResult:
        plan = get_plan(context.user.subscription_tier)
        c = message.content
        kind = "voice note" if c.voice else "audio message"

        if not plan.can_transcribe_audio:
            return HandlerResult(
                processed_content=(
                    f"User sent a {kind}, but their {plan.display_name} plan doesn't include "
                    "voice transcription. Politely tell them and offer to upgrade for voice support."
                ),
                requires_ai=True,
            )

        if not c.media_id:
            return HandlerResult(
                processed_content=f"User sent a {kind} but no media id was attached.",
                requires_ai=True,
            )

        try:
            data, mime_type = await process_incoming_media(c.media_id)
            transcript = await _transcribe(data, mime_type)
            if transcript:
                logger.info(f"🎙️ Transcribed {kind}: {transcript[:100]}")
                return HandlerResult(
                    processed_content=f"(Transcribed {kind}) {transcript}",
                    requires_ai=True,
                )
            return HandlerResult(
                processed_content=(
                    f"User sent a {kind} but transcription failed. Apologize briefly "
                    "and ask them to type the question."
                ),
                requires_ai=True,
            )
        except Exception as e:
            logger.error(f"Audio handler failed: {e}")
            return HandlerResult(
                processed_content=(
                    f"User sent a {kind} that failed to download. Ask them to retry."
                ),
                requires_ai=True,
            )
