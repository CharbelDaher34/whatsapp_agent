"""WhatsApp API client for sending messages."""
import httpx
from typing import Optional
from app.core.config import settings
from app.core.logging import logger


async def send_whatsapp_text(to: str, message: str):
    """Send a text message via WhatsApp Business API."""
    # Clean phone ID (remove any leading = or whitespace)
    phone_id = settings.WHATSAPP_PHONE_ID.strip().lstrip('=')
    url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message[:4000]},  # WhatsApp limit
    }
    
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"Message sent to {to}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Error sending WhatsApp message: {e}")
        logger.error(f"Response: {e.response.text}")
        logger.error(f"URL: {url}")
        logger.error(f"Phone ID from config: {settings.WHATSAPP_PHONE_ID}")

    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {e}")


async def get_media_url(media_id: str) -> str:
    """Get the download URL for a media ID."""
    url = f"https://graph.facebook.com/v20.0/{media_id}"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get("url")


async def download_media(media_url: str) -> bytes:
    """Download media content from WhatsApp URL."""
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(media_url, headers=headers)
        response.raise_for_status()
        return response.content


async def send_whatsapp_image(to: str, image_url: str = None, media_id: str = None, caption: str = None):
    """Send an image message via WhatsApp Business API."""
    if not image_url and not media_id:
        logger.error("Either image_url or media_id must be provided")
        return

    phone_id = settings.WHATSAPP_PHONE_ID.strip().lstrip('=')
    url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
    }
    
    if media_id:
        payload["image"] = {"id": media_id}
    else:
        payload["image"] = {"link": image_url}
    
    if caption:
        payload["image"]["caption"] = caption
    
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"Image sent to {to}")
    except Exception as e:
        logger.error(f"Error sending WhatsApp image: {e}")


async def send_typing_indicator(to: str, is_typing: bool = True) -> bool:
    """
    Send typing indicator (shows "typing..." in chat).
    
    Note: WhatsApp Cloud API doesn't officially support typing indicators.
    This is a placeholder for future implementation or webhook-based approach.
    
    Args:
        to: Phone number to send to
        is_typing: True to show typing, False to clear
        
    Returns:
        True if sent successfully
    """
    # WhatsApp Cloud API doesn't have direct typing indicator support
    # You can implement this by sending a dummy "is_typing" via webhook
    # or wait for official API support
    logger.debug(f"Typing indicator for {to}: {is_typing}")
    return True


async def send_location(
    to: str,
    latitude: float,
    longitude: float,
    name: Optional[str] = None,
    address: Optional[str] = None
) -> bool:
    """
    Send location message.
    
    Args:
        to: Phone number to send to
        latitude: Location latitude
        longitude: Location longitude
        name: Location name (optional)
        address: Location address (optional)
        
    Returns:
        True if sent successfully
    """
    phone_id = settings.WHATSAPP_PHONE_ID.strip().lstrip('=')
    url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
    
    location_data = {
        "latitude": latitude,
        "longitude": longitude
    }
    
    if name:
        location_data["name"] = name
    if address:
        location_data["address"] = address
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "location",
        "location": location_data
    }
    
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"✅ Location sent to {to}")
            return True
    except Exception as e:
        logger.error(f"❌ Error sending location: {e}")
        return False


async def upload_media(file_path: str, mime_type: str = None) -> str:
    """
    Upload media to WhatsApp and return the media ID.
    Required for sending local files.
    
    Reference: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media/#upload-media
    """
    import os
    import mimetypes
    
    # Auto-detect MIME type if not provided
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            # Default to image/jpeg for images
            if file_path.lower().endswith(('.jpg', '.jpeg')):
                mime_type = 'image/jpeg'
            elif file_path.lower().endswith('.png'):
                mime_type = 'image/png'
            else:
                mime_type = 'application/octet-stream'
    
    logger.info(f"📤 Uploading media: {file_path} (type: {mime_type})")
    
    # Verify file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Media file not found: {file_path}")
    
    phone_id = settings.WHATSAPP_PHONE_ID.strip().lstrip('=')
    url = f"https://graph.facebook.com/v20.0/{phone_id}/media"
    
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            with open(file_path, "rb") as f:
                files = {
                    "file": (os.path.basename(file_path), f, mime_type)
                }
                data = {
                    "messaging_product": "whatsapp",
                    "type": mime_type
                }
                response = await client.post(url, headers=headers, data=data, files=files)
                response.raise_for_status()
                media_id = response.json().get("id")
                logger.info(f"✅ Media uploaded successfully: {media_id}")
                return media_id
    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error uploading media: {e}")
        if hasattr(e, 'response'):
            logger.error(f"Response: {e.response.text if hasattr(e.response, 'text') else e.response}")
        raise



