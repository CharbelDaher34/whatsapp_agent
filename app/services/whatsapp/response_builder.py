"""WhatsApp response payload builder."""
from typing import Optional, Dict, Any
from pydantic import BaseModel
from app.core.logging import logger


class WhatsAppResponse(BaseModel):
    """Structured WhatsApp response."""
    to: str
    type: str  # text, image, video, etc.
    text: Optional[str] = None
    media_id: Optional[str] = None
    caption: Optional[str] = None
    image_url: Optional[str] = None


def build_text_response(message: str, phone: str) -> WhatsAppResponse:
    """
    Build a text message response.
    
    Args:
        message: Text message to send
        phone: Recipient phone number
        
    Returns:
        WhatsAppResponse object
    """
    return WhatsAppResponse(
        to=phone,
        type="text",
        text=message
    )


def build_image_response(
    media_id: Optional[str],
    caption: Optional[str],
    phone: str,
    image_url: Optional[str] = None
) -> WhatsAppResponse:
    """
    Build an image message response.
    
    Args:
        media_id: WhatsApp media ID
        caption: Image caption
        phone: Recipient phone number
        image_url: Optional direct image URL
        
    Returns:
        WhatsAppResponse object
    """
    return WhatsAppResponse(
        to=phone,
        type="image",
        media_id=media_id,
        caption=caption,
        image_url=image_url
    )


def build_error_response(error_msg: str, phone: str) -> WhatsAppResponse:
    """
    Build an error message response.
    
    Args:
        error_msg: Error message
        phone: Recipient phone number
        
    Returns:
        WhatsAppResponse object
    """
    friendly_msg = "Sorry, I encountered an error processing your message. Please try again."
    logger.error(f"Building error response: {error_msg}")
    
    return WhatsAppResponse(
        to=phone,
        type="text",
        text=friendly_msg
    )


def build_rate_limit_response(phone: str) -> WhatsAppResponse:
    """
    Build a rate limit exceeded response.
    
    Args:
        phone: Recipient phone number
        
    Returns:
        WhatsAppResponse object
    """
    message = (
        "You've reached your daily message limit. "
        "Please upgrade your subscription for unlimited messages."
    )
    
    return WhatsAppResponse(
        to=phone,
        type="text",
        text=message
    )


def response_to_dict(response: WhatsAppResponse) -> Dict[str, Any]:
    """
    Convert WhatsAppResponse to dict for sending.
    
    Args:
        response: WhatsAppResponse object
        
    Returns:
        Dict ready for WhatsApp API
    """
    result = {
        "type": response.type,
        "to": response.to
    }
    
    if response.type == "text" and response.text:
        result["message"] = response.text
    elif response.type == "image":
        result["media_id"] = response.media_id
        result["image_url"] = response.image_url
        result["caption"] = response.caption
    
    return result

