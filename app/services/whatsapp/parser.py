"""WhatsApp webhook payload parser."""
from typing import Optional
from pydantic import BaseModel
from enum import Enum
from app.core.logging import logger
from app.core.exceptions import ParseError


class MessageType(str, Enum):
    """WhatsApp message types."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    INTERACTIVE = "interactive"
    LOCATION = "location"
    CONTACTS = "contacts"
    UNKNOWN = "unknown"


class MessageContent(BaseModel):
    """Extracted message content."""
    text: str = ""
    media_id: Optional[str] = None
    media_url: Optional[str] = None
    mime_type: Optional[str] = None
    caption: Optional[str] = None
    button_id: Optional[str] = None
    button_title: Optional[str] = None
    list_id: Optional[str] = None
    list_title: Optional[str] = None


class ParsedMessage(BaseModel):
    """Parsed WhatsApp message."""
    from_phone: str
    message_id: str
    message_type: MessageType
    content: MessageContent
    timestamp: Optional[int] = None
    raw_message: dict


def parse_webhook_payload(payload: dict) -> Optional[ParsedMessage]:
    """
    Parse WhatsApp webhook payload and extract message data.
    
    Args:
        payload: Raw webhook payload from WhatsApp
        
    Returns:
        ParsedMessage if valid message found, None otherwise
        
    Raises:
        ParseError: If payload structure is invalid
    """
    try:
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages")
        
        if not messages:
            # Not a message event (status update, etc.)
            if value.get("statuses"):
                logger.debug("Status update received, skipping")
            return None
        
        msg = messages[0]
        from_phone = msg["from"]
        msg_id = msg.get("id")
        msg_type_str = msg["type"]
        timestamp = msg.get("timestamp")
        
        # Determine message type
        try:
            msg_type = MessageType(msg_type_str)
        except ValueError:
            msg_type = MessageType.UNKNOWN
            logger.warning(f"Unknown message type: {msg_type_str}")
        
        # Extract message content based on type
        content = extract_message_content(msg, msg_type)
        
        return ParsedMessage(
            from_phone=from_phone,
            message_id=msg_id,
            message_type=msg_type,
            content=content,
            timestamp=timestamp,
            raw_message=msg
        )
        
    except (KeyError, IndexError) as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise ParseError(f"Invalid payload structure: {e}")


def extract_message_content(message: dict, msg_type: MessageType) -> MessageContent:
    """
    Extract content from a WhatsApp message based on its type.
    
    Args:
        message: Raw message dict from webhook
        msg_type: Message type enum
        
    Returns:
        MessageContent with extracted data
    """
    content = MessageContent()
    
    if msg_type == MessageType.TEXT:
        content.text = message.get("text", {}).get("body", "")
    
    elif msg_type == MessageType.IMAGE:
        image_data = message.get("image", {})
        content.media_id = image_data.get("id")
        content.mime_type = image_data.get("mime_type")
        content.caption = image_data.get("caption", "")
        content.text = content.caption
    
    elif msg_type == MessageType.VIDEO:
        video_data = message.get("video", {})
        content.media_id = video_data.get("id")
        content.mime_type = video_data.get("mime_type")
        content.caption = video_data.get("caption", "")
        content.text = content.caption
    
    elif msg_type == MessageType.AUDIO:
        audio_data = message.get("audio", {})
        content.media_id = audio_data.get("id")
        content.mime_type = audio_data.get("mime_type")
        content.text = "[Audio message]"
    
    elif msg_type == MessageType.DOCUMENT:
        doc_data = message.get("document", {})
        content.media_id = doc_data.get("id")
        content.mime_type = doc_data.get("mime_type")
        content.caption = doc_data.get("caption", "")
        content.text = content.caption or "[Document]"
    
    elif msg_type == MessageType.INTERACTIVE:
        interactive = message.get("interactive", {})
        interactive_type = interactive.get("type")
        
        if interactive_type == "button_reply":
            button_reply = interactive.get("button_reply", {})
            content.button_id = button_reply.get("id")
            content.button_title = button_reply.get("title")
            content.text = f"[Button: {content.button_title}]"
            logger.info(f"Button clicked: {content.button_title} ({content.button_id})")
        
        elif interactive_type == "list_reply":
            list_reply = interactive.get("list_reply", {})
            content.list_id = list_reply.get("id")
            content.list_title = list_reply.get("title")
            content.text = f"[List: {content.list_title}]"
            logger.info(f"List selected: {content.list_title} ({content.list_id})")
        
        else:
            content.text = f"[Interactive: {interactive_type}]"
    
    else:
        content.text = f"[{msg_type.value} message not supported]"
    
    return content

