"""Pydantic schemas for WhatsApp webhook payloads."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


# Message Type Schemas
class TextMessage(BaseModel):
    """Text message content."""
    body: str


class MediaMessage(BaseModel):
    """Media message content (image, video, audio, document)."""
    id: str
    mime_type: Optional[str] = None
    sha256: Optional[str] = None
    caption: Optional[str] = None


class LocationMessage(BaseModel):
    """Location message content."""
    latitude: float
    longitude: float
    name: Optional[str] = None
    address: Optional[str] = None


class ContactMessage(BaseModel):
    """Contact message content."""
    name: Dict[str, Any]
    phones: Optional[List[Dict[str, str]]] = None
    emails: Optional[List[Dict[str, str]]] = None


class InteractiveButtonReply(BaseModel):
    """Interactive button reply."""
    id: str
    title: str


class InteractiveListReply(BaseModel):
    """Interactive list reply."""
    id: str
    title: str
    description: Optional[str] = None


class InteractiveMessage(BaseModel):
    """Interactive message content (button or list reply)."""
    type: Literal["button_reply", "list_reply"]
    button_reply: Optional[InteractiveButtonReply] = None
    list_reply: Optional[InteractiveListReply] = None


class ReactionMessage(BaseModel):
    """Reaction message content."""
    message_id: str
    emoji: str


class ContextMessage(BaseModel):
    """Message context (reply to another message)."""
    from_: Optional[str] = Field(None, alias="from")
    id: str
    forwarded: Optional[bool] = None
    frequently_forwarded: Optional[bool] = None


# Main Message Schema
class WebhookMessage(BaseModel):
    """WhatsApp webhook message object."""
    from_: str = Field(..., alias="from")
    id: str
    timestamp: str
    type: Literal[
        "text", "image", "video", "audio", "document", 
        "voice", "sticker", "location", "contacts", 
        "interactive", "button", "reaction", "unsupported"
    ]
    
    # Optional fields based on message type
    text: Optional[TextMessage] = None
    image: Optional[MediaMessage] = None
    video: Optional[MediaMessage] = None
    audio: Optional[MediaMessage] = None
    document: Optional[MediaMessage] = None
    voice: Optional[MediaMessage] = None
    location: Optional[LocationMessage] = None
    contacts: Optional[List[ContactMessage]] = None
    interactive: Optional[InteractiveMessage] = None
    button: Optional[Dict[str, Any]] = None
    reaction: Optional[ReactionMessage] = None
    context: Optional[ContextMessage] = None


# Status Update Schemas
class StatusUpdate(BaseModel):
    """Message status update."""
    id: str
    status: Literal["sent", "delivered", "read", "failed"]
    timestamp: str
    recipient_id: str
    conversation: Optional[Dict[str, Any]] = None
    pricing: Optional[Dict[str, Any]] = None
    errors: Optional[List[Dict[str, Any]]] = None


# Profile Schema
class Profile(BaseModel):
    """User profile information."""
    name: str


class Contact(BaseModel):
    """Contact information."""
    profile: Profile
    wa_id: str


# Value Schema (contains messages or statuses)
class WebhookValue(BaseModel):
    """Webhook value object."""
    messaging_product: Literal["whatsapp"]
    metadata: Dict[str, Any]
    contacts: Optional[List[Contact]] = None
    messages: Optional[List[WebhookMessage]] = None
    statuses: Optional[List[StatusUpdate]] = None


# Change Schema
class WebhookChange(BaseModel):
    """Webhook change object."""
    value: WebhookValue
    field: Literal["messages"]


# Entry Schema
class WebhookEntry(BaseModel):
    """Webhook entry object."""
    id: str
    changes: List[WebhookChange]


# Root Webhook Schema
class WebhookPayload(BaseModel):
    """Complete WhatsApp webhook payload."""
    object: Literal["whatsapp_business_account"]
    entry: List[WebhookEntry]


# Verification Request Schema
class VerificationRequest(BaseModel):
    """Webhook verification request parameters."""
    hub_mode: str = Field(..., alias="hub.mode")
    hub_challenge: str = Field(..., alias="hub.challenge")
    hub_verify_token: str = Field(..., alias="hub.verify_token")
    
    class Config:
        populate_by_name = True


# Interactive Message Payloads (for sending)
class ButtonAction(BaseModel):
    """Button action for interactive messages."""
    type: Literal["reply"]
    reply: Dict[str, str]  # {"id": "button_id", "title": "Button Title"}


class InteractiveButton(BaseModel):
    """Interactive button message structure."""
    type: Literal["button"]
    body: Dict[str, str]  # {"text": "Message body"}
    action: Dict[str, List[ButtonAction]]


class ListSection(BaseModel):
    """List section for interactive list messages."""
    title: str
    rows: List[Dict[str, str]]  # [{"id": "row_id", "title": "Row Title", "description": "..."}]


class InteractiveList(BaseModel):
    """Interactive list message structure."""
    type: Literal["list"]
    header: Optional[Dict[str, str]] = None  # {"type": "text", "text": "Header"}
    body: Dict[str, str]  # {"text": "Message body"}
    footer: Optional[Dict[str, str]] = None  # {"text": "Footer text"}
    action: Dict[str, Any]  # {"button": "Menu", "sections": [...]}

