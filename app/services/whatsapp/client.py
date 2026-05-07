"""Thin wrapper around the WhatsApp Cloud API send endpoints.

Media downloads and uploads live in ``media_handler.py``; this module only
covers outbound messages (text, image, location). Interactive messages
(buttons / lists / reactions / read receipts) live in ``interactive.py``.
"""
from typing import Optional

import httpx

from app.core.config import settings
from app.core.logging import logger


def _phone_id() -> str:
    return settings.WHATSAPP_PHONE_ID.strip().lstrip("=")


def _messages_url() -> str:
    return f"https://graph.facebook.com/v20.0/{_phone_id()}/messages"


def _auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }


async def send_whatsapp_text(to: str, message: str) -> bool:
    """Send a plain text WhatsApp message. Returns True on success."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": (message or "")[:4000]},  # WhatsApp body cap
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(_messages_url(), json=payload, headers=_auth_headers())
            response.raise_for_status()
            logger.info(f"📤 Text sent to {to}")
            return True
    except httpx.HTTPStatusError as e:
        logger.error(f"WhatsApp text send failed ({e.response.status_code}): {e.response.text[:300]}")
    except Exception as e:
        logger.error(f"WhatsApp text send error: {e}")
    return False


async def send_whatsapp_image(
    to: str,
    image_url: Optional[str] = None,
    media_id: Optional[str] = None,
    caption: Optional[str] = None,
) -> bool:
    """Send an image, either by uploaded ``media_id`` or by public ``image_url``."""
    if not (image_url or media_id):
        logger.error("send_whatsapp_image requires image_url or media_id")
        return False

    image_block: dict = {"id": media_id} if media_id else {"link": image_url}
    if caption:
        image_block["caption"] = caption[:1024]

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": image_block,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(_messages_url(), json=payload, headers=_auth_headers())
            response.raise_for_status()
            logger.info(f"📤 Image sent to {to}")
            return True
    except Exception as e:
        logger.error(f"WhatsApp image send error: {e}")
        return False


async def send_location(
    to: str,
    latitude: float,
    longitude: float,
    name: Optional[str] = None,
    address: Optional[str] = None,
) -> bool:
    """Send a location pin."""
    block: dict = {"latitude": latitude, "longitude": longitude}
    if name:
        block["name"] = name
    if address:
        block["address"] = address
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "location",
        "location": block,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(_messages_url(), json=payload, headers=_auth_headers())
            response.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"WhatsApp location send error: {e}")
        return False
