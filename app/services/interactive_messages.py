"""Helper functions for WhatsApp interactive messages."""
from typing import List, Dict, Optional, Any
from app.core.config import settings
from app.core.logging import logger
import httpx


async def send_button_message(
    to: str,
    body_text: str,
    buttons: List[Dict[str, str]],
    header_text: Optional[str] = None,
    footer_text: Optional[str] = None
) -> bool:
    """
    Send interactive button message to WhatsApp user.
    
    Args:
        to: Phone number to send to
        body_text: Main message body
        buttons: List of button dicts with 'id' and 'title' keys (max 3 buttons)
        header_text: Optional header text
        footer_text: Optional footer text
        
    Returns:
        True if sent successfully, False otherwise
        
    Example:
        await send_button_message(
            to="1234567890",
            body_text="Choose an option:",
            buttons=[
                {"id": "opt1", "title": "Option 1"},
                {"id": "opt2", "title": "Option 2"}
            ]
        )
    
    Reference: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages#interactive-object
    """
    if len(buttons) > 3:
        logger.warning("WhatsApp allows max 3 buttons, truncating")
        buttons = buttons[:3]
    
    phone_id = settings.WHATSAPP_PHONE_ID.strip().lstrip('=')
    url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
    
    # Build button actions
    button_actions = []
    for btn in buttons:
        button_actions.append({
            "type": "reply",
            "reply": {
                "id": btn["id"],
                "title": btn["title"][:20]  # WhatsApp limit
            }
        })
    
    # Build interactive message
    interactive = {
        "type": "button",
        "body": {"text": body_text},
        "action": {"buttons": button_actions}
    }
    
    if header_text:
        interactive["header"] = {"type": "text", "text": header_text}
    
    if footer_text:
        interactive["footer"] = {"text": footer_text}
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": interactive
    }
    
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"✅ Button message sent to {to}")
            return True
    except Exception as e:
        logger.error(f"❌ Error sending button message: {e}")
        return False


async def send_list_message(
    to: str,
    body_text: str,
    button_text: str,
    sections: List[Dict[str, Any]],
    header_text: Optional[str] = None,
    footer_text: Optional[str] = None
) -> bool:
    """
    Send interactive list message to WhatsApp user.
    
    Args:
        to: Phone number to send to
        body_text: Main message body
        button_text: Text for the list button (e.g., "View Menu")
        sections: List of sections, each with 'title' and 'rows'
        header_text: Optional header text
        footer_text: Optional footer text
        
    Returns:
        True if sent successfully, False otherwise
        
    Example:
        await send_list_message(
            to="1234567890",
            body_text="Choose from our menu:",
            button_text="View Menu",
            sections=[
                {
                    "title": "Main Dishes",
                    "rows": [
                        {"id": "item1", "title": "Pizza", "description": "Cheese pizza"},
                        {"id": "item2", "title": "Pasta", "description": "Italian pasta"}
                    ]
                }
            ]
        )
    
    Reference: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages#interactive-object
    """
    phone_id = settings.WHATSAPP_PHONE_ID.strip().lstrip('=')
    url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
    
    # Build interactive message
    interactive = {
        "type": "list",
        "body": {"text": body_text},
        "action": {
            "button": button_text[:20],  # WhatsApp limit
            "sections": sections
        }
    }
    
    if header_text:
        interactive["header"] = {"type": "text", "text": header_text}
    
    if footer_text:
        interactive["footer"] = {"text": footer_text}
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": interactive
    }
    
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"✅ List message sent to {to}")
            return True
    except Exception as e:
        logger.error(f"❌ Error sending list message: {e}")
        return False


async def mark_message_read(message_id: str) -> bool:
    """
    Mark a message as read.
    
    Args:
        message_id: WhatsApp message ID (WAMID)
        
    Returns:
        True if marked successfully, False otherwise
        
    Reference: https://developers.facebook.com/docs/whatsapp/cloud-api/guides/mark-messages-as-read
    """
    phone_id = settings.WHATSAPP_PHONE_ID.strip().lstrip('=')
    url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
    
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id
    }
    
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.debug(f"✅ Message {message_id} marked as read")
            return True
    except Exception as e:
        logger.error(f"❌ Error marking message as read: {e}")
        return False


async def send_reaction(message_id: str, emoji: str, to: str) -> bool:
    """
    Send a reaction emoji to a message.
    
    Args:
        message_id: WhatsApp message ID (WAMID) to react to
        emoji: Emoji to react with (single emoji)
        to: Phone number of the recipient
        
    Returns:
        True if sent successfully, False otherwise
        
    Reference: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages#reaction-object
    """
    phone_id = settings.WHATSAPP_PHONE_ID.strip().lstrip('=')
    url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "reaction",
        "reaction": {
            "message_id": message_id,
            "emoji": emoji
        }
    }
    
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.debug(f"✅ Reaction {emoji} sent to message {message_id}")
            return True
    except Exception as e:
        logger.error(f"❌ Error sending reaction: {e}")
        return False

