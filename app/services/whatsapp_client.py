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


