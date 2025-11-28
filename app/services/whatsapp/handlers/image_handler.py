"""Image message handler."""
import os
import redis.asyncio as redis
from datetime import datetime
from app.services.whatsapp.handlers.base import BaseMessageHandler, HandlerResult
from app.services.whatsapp.parser import ParsedMessage
from app.services.conversation.flow_service import ConversationContext
from app.services.whatsapp.media_handler import process_incoming_media
from app.core.config import settings
from app.core.logging import logger


# Redis key for storing current user image path
def _get_user_image_key(phone: str) -> str:
    return f"user_image:{phone}"


async def get_user_current_image(phone: str) -> str | None:
    """Get the current image path for a user from Redis."""
    try:
        r = redis.from_url(settings.REDIS_URL)
        path = await r.get(_get_user_image_key(phone))
        await r.aclose()
        return path.decode() if path else None
    except Exception as e:
        logger.error(f"Failed to get user image from Redis: {e}")
        return None


async def set_user_current_image(phone: str, image_path: str) -> None:
    """Store the current image path for a user in Redis (expires in 10 min)."""
    try:
        r = redis.from_url(settings.REDIS_URL)
        await r.setex(_get_user_image_key(phone), 600, image_path)  # 10 min TTL
        await r.aclose()
        logger.info(f"📍 Stored image path in Redis for {phone}: {image_path}")
    except Exception as e:
        logger.error(f"Failed to store user image in Redis: {e}")


class ImageHandler(BaseMessageHandler):
    """Handler for image messages."""
    
    async def handle(
        self,
        message: ParsedMessage,
        context: ConversationContext
    ) -> HandlerResult:
        """Handle image message - download, save to disk, store path in Redis."""
        media_data = None
        media_type = None
        saved_image_path = None
        
        if message.content.media_id:
            try:
                media_data, media_type = await process_incoming_media(message.content.media_id)
                logger.info(f"Downloaded image ({len(media_data)} bytes, {media_type})")
                
                # Save image to disk
                saved_image_path = await self._save_incoming_image(
                    media_data, 
                    message.content.media_id,
                    media_type
                )
                logger.info(f"Saved incoming image to: {saved_image_path}")
                
                # Store path in Redis so tools can access it deterministically
                await set_user_current_image(message.from_phone, saved_image_path)
                
            except Exception as e:
                logger.error(f"Failed to download image: {e}")
        
        # Simple content - no need to embed path, tools will get it from Redis
        user_caption = message.content.caption or ""
        content = user_caption or "I sent you an image. What do you see?"
        
        return HandlerResult(
            processed_content=content,
            media_data=media_data,
            media_type=media_type,
            requires_ai=True
        )
    
    async def _save_incoming_image(self, data: bytes, media_id: str, media_type: str) -> str:
        """Save incoming image to disk and return the path."""
        os.makedirs("images", exist_ok=True)
        
        # Determine extension from media type
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

