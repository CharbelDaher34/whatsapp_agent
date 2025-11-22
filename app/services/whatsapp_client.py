"""WhatsApp API client for sending messages."""
import httpx
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


async def upload_media(file_path: str, mime_type: str = "image/jpeg") -> str:
    """
    Upload media to WhatsApp and return the media ID.
    Required for sending local files.
    """
    phone_id = settings.WHATSAPP_PHONE_ID.strip().lstrip('=')
    url = f"https://graph.facebook.com/v20.0/{phone_id}/media"
    
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
    }
    
    try:
        async with httpx.AsyncClient() as client:
            with open(file_path, "rb") as f:
                files = {
                    "file": (file_path.split("/")[-1], f, mime_type)
                }
                data = {
                    "messaging_product": "whatsapp"
                }
                response = await client.post(url, headers=headers, data=data, files=files)
                response.raise_for_status()
                return response.json().get("id")
    except Exception as e:
        logger.error(f"Error uploading media: {e}")
        raise



