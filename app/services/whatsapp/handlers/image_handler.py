"""Image message handler.

Downloads the image, persists it to disk, and remembers the path in Redis so
the image_to_image tool can find it deterministically when the agent decides
to call it later.
"""
import os
from datetime import datetime

import redis.asyncio as redis

from app.services.whatsapp.handlers.base import BaseMessageHandler, HandlerResult
from app.services.whatsapp.parser import ParsedMessage
from app.services.conversation.flow_service import ConversationContext
from app.services.whatsapp.media_handler import process_incoming_media
from app.core.config import settings
from app.core.logging import logger


def _get_user_image_key(phone: str) -> str:
    return f"user_image:{phone}"


async def get_user_current_image(phone: str) -> str | None:
    """Return the path of the most-recent image the user uploaded, if any."""
    try:
        r = redis.from_url(settings.REDIS_URL)
        try:
            path = await r.get(_get_user_image_key(phone))
            return path.decode() if path else None
        finally:
            await r.aclose()
    except Exception as e:
        logger.error(f"Failed to read user image from Redis: {e}")
        return None


async def set_user_current_image(phone: str, image_path: str) -> None:
    """Cache the path under a 10-minute TTL so transforms can pick it up."""
    try:
        r = redis.from_url(settings.REDIS_URL)
        try:
            await r.setex(_get_user_image_key(phone), 600, image_path)
        finally:
            await r.aclose()
        logger.info(f"📍 Stored image path for {phone}: {image_path}")
    except Exception as e:
        logger.error(f"Failed to store user image in Redis: {e}")


class ImageHandler(BaseMessageHandler):
    async def handle(
        self,
        message: ParsedMessage,
        context: ConversationContext,
    ) -> HandlerResult:
        media_data: bytes | None = None
        media_type: str | None = None

        if not message.content.media_id:
            return HandlerResult(
                processed_content="User sent an image but media id was missing.",
                requires_ai=True,
            )

        try:
            media_data, media_type = await process_incoming_media(message.content.media_id)
            saved = await self._save_incoming_image(media_data, message.content.media_id, media_type)
            await set_user_current_image(message.from_phone, saved)
            logger.info(f"Image saved to {saved} ({len(media_data)} bytes, {media_type})")
        except Exception as e:
            logger.error(f"Image download failed: {e}")
            # Fall through with no media bytes; AI can still respond.

        caption = message.content.caption or ""
        if caption:
            processed = caption
        else:
            processed = "I sent you an image. Take a look and respond."

        return HandlerResult(
            processed_content=processed,
            media_data=media_data,
            media_type=media_type,
            requires_ai=True,
        )

    async def _save_incoming_image(
        self, data: bytes, media_id: str, media_type: str | None,
    ) -> str:
        os.makedirs("images", exist_ok=True)
        ext = "jpg"
        if media_type:
            if "png" in media_type:
                ext = "png"
            elif "webp" in media_type:
                ext = "webp"
            elif "gif" in media_type:
                ext = "gif"
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"incoming_{media_id[:8]}_{timestamp}.{ext}"
        filepath = os.path.join("images", filename)
        with open(filepath, "wb") as f:
            f.write(data)
        return filepath
