"""WhatsApp webhook payload parser.

Supports every inbound type WhatsApp Cloud API can deliver:
text, image, video, audio (incl. voice), document, sticker, location,
contacts, interactive (button/list reply), button (template button),
reaction, unsupported.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from enum import Enum

from app.core.logging import logger
from app.core.exceptions import ParseError


class MessageType(str, Enum):
    """WhatsApp message types we recognize."""

    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"           # voice notes; treated like audio
    DOCUMENT = "document"
    STICKER = "sticker"
    INTERACTIVE = "interactive"
    BUTTON = "button"          # template-button reply (legacy)
    REACTION = "reaction"
    LOCATION = "location"
    CONTACTS = "contacts"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class MessageContent(BaseModel):
    """Extracted message content (one DTO covering all types)."""

    text: str = ""

    # Media
    media_id: Optional[str] = None
    media_url: Optional[str] = None
    mime_type: Optional[str] = None
    caption: Optional[str] = None
    filename: Optional[str] = None
    voice: bool = False  # set when message is a voice note

    # Interactive replies
    button_id: Optional[str] = None
    button_title: Optional[str] = None
    list_id: Optional[str] = None
    list_title: Optional[str] = None

    # Reaction
    reaction_emoji: Optional[str] = None
    reaction_target_id: Optional[str] = None

    # Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    location_address: Optional[str] = None

    # Contacts
    contacts: Optional[List[Dict[str, Any]]] = None

    # Sticker
    animated: Optional[bool] = None


class ParsedMessage(BaseModel):
    """Parsed WhatsApp message ready for downstream handlers."""

    from_phone: str
    message_id: str
    message_type: MessageType
    content: MessageContent
    timestamp: Optional[int] = None
    raw_message: dict


def parse_webhook_payload(payload: dict) -> Optional[ParsedMessage]:
    """Parse a WhatsApp webhook payload.

    Returns None for non-message events (statuses, errors). Raises ParseError
    only on malformed envelopes — handlers downstream tolerate unknown content.
    """
    try:
        entry = payload.get("entry") or []
        if not entry:
            return None
        changes = entry[0].get("changes") or []
        if not changes:
            return None
        value = changes[0].get("value") or {}
        messages = value.get("messages")

        if not messages:
            if value.get("statuses"):
                logger.debug("Status update received, skipping")
            return None

        msg = messages[0]
        from_phone = msg.get("from")
        msg_id = msg.get("id")
        if not from_phone or not msg_id:
            raise ParseError("Missing 'from' or 'id' on message")

        msg_type_str = msg.get("type") or "unknown"
        try:
            msg_type = MessageType(msg_type_str)
        except ValueError:
            logger.warning(f"Unknown message type from WhatsApp: {msg_type_str}")
            msg_type = MessageType.UNKNOWN

        timestamp_raw = msg.get("timestamp")
        try:
            timestamp = int(timestamp_raw) if timestamp_raw else None
        except (TypeError, ValueError):
            timestamp = None

        content = extract_message_content(msg, msg_type)

        return ParsedMessage(
            from_phone=from_phone,
            message_id=msg_id,
            message_type=msg_type,
            content=content,
            timestamp=timestamp,
            raw_message=msg,
        )

    except ParseError:
        raise
    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise ParseError(f"Invalid payload structure: {e}")


def _media_block(message: dict, key: str) -> dict:
    """Safely fetch the media sub-block (image/video/...) from a message."""
    return message.get(key) or {}


def extract_message_content(message: dict, msg_type: MessageType) -> MessageContent:
    """Extract structured content based on message type."""
    content = MessageContent()

    if msg_type == MessageType.TEXT:
        content.text = message.get("text", {}).get("body", "")

    elif msg_type == MessageType.IMAGE:
        block = _media_block(message, "image")
        content.media_id = block.get("id")
        content.mime_type = block.get("mime_type")
        content.caption = block.get("caption", "")
        content.text = content.caption or ""

    elif msg_type == MessageType.VIDEO:
        block = _media_block(message, "video")
        content.media_id = block.get("id")
        content.mime_type = block.get("mime_type")
        content.caption = block.get("caption", "")
        content.text = content.caption or ""

    elif msg_type in (MessageType.AUDIO, MessageType.VOICE):
        block = _media_block(message, "audio") or _media_block(message, "voice")
        content.media_id = block.get("id")
        content.mime_type = block.get("mime_type")
        content.voice = bool(block.get("voice")) or msg_type == MessageType.VOICE
        content.text = "[Voice note]" if content.voice else "[Audio message]"

    elif msg_type == MessageType.DOCUMENT:
        block = _media_block(message, "document")
        content.media_id = block.get("id")
        content.mime_type = block.get("mime_type")
        content.caption = block.get("caption", "")
        content.filename = block.get("filename")
        content.text = content.caption or f"[Document: {content.filename or 'untitled'}]"

    elif msg_type == MessageType.STICKER:
        block = _media_block(message, "sticker")
        content.media_id = block.get("id")
        content.mime_type = block.get("mime_type")
        content.animated = bool(block.get("animated"))
        content.text = "[Animated sticker]" if content.animated else "[Sticker]"

    elif msg_type == MessageType.INTERACTIVE:
        interactive = message.get("interactive", {})
        kind = interactive.get("type")
        if kind == "button_reply":
            br = interactive.get("button_reply", {})
            content.button_id = br.get("id")
            content.button_title = br.get("title")
            content.text = content.button_title or ""
        elif kind == "list_reply":
            lr = interactive.get("list_reply", {})
            content.list_id = lr.get("id")
            content.list_title = lr.get("title")
            content.text = content.list_title or ""
        else:
            content.text = f"[Interactive: {kind}]"

    elif msg_type == MessageType.BUTTON:
        btn = message.get("button", {})
        content.button_id = btn.get("payload")
        content.button_title = btn.get("text")
        content.text = content.button_title or ""

    elif msg_type == MessageType.REACTION:
        rx = message.get("reaction", {})
        content.reaction_emoji = rx.get("emoji")
        content.reaction_target_id = rx.get("message_id")
        content.text = f"[Reacted with {content.reaction_emoji or 'emoji'}]"

    elif msg_type == MessageType.LOCATION:
        loc = message.get("location", {})
        try:
            content.latitude = float(loc.get("latitude"))
            content.longitude = float(loc.get("longitude"))
        except (TypeError, ValueError):
            content.latitude = None
            content.longitude = None
        content.location_name = loc.get("name")
        content.location_address = loc.get("address")
        bits = [content.location_name, content.location_address]
        label = ", ".join(b for b in bits if b) or "shared location"
        if content.latitude is not None and content.longitude is not None:
            content.text = f"[Location: {label} ({content.latitude:.5f}, {content.longitude:.5f})]"
        else:
            content.text = f"[Location: {label}]"

    elif msg_type == MessageType.CONTACTS:
        contacts = message.get("contacts") or []
        # keep raw payload for AI; build a short label too
        content.contacts = contacts
        names = []
        for c in contacts:
            n = c.get("name") or {}
            names.append(n.get("formatted_name") or n.get("first_name") or "contact")
        content.text = "[Shared contacts: " + ", ".join(names) + "]" if names else "[Shared contacts]"

    elif msg_type == MessageType.UNSUPPORTED:
        content.text = "[Unsupported WhatsApp message type]"

    else:
        content.text = f"[{msg_type.value} message]"

    return content
