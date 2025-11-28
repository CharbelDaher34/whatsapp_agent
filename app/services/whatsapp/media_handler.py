"""WhatsApp media handling service."""
import os
import re
import mimetypes
from typing import Optional, Tuple
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import MediaProcessingError


async def download_media_from_url(media_url: str, media_id: str) -> bytes:
    """
    Download media from WhatsApp media URL.
    
    Args:
        media_url: URL to download from
        media_id: Media ID for logging
        
    Returns:
        Media binary data
        
    Raises:
        MediaProcessingError: If download fails
    """
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(media_url, headers=headers)
            response.raise_for_status()
            logger.info(f"Downloaded media {media_id} ({len(response.content)} bytes)")
            return response.content
    except Exception as e:
        logger.error(f"Failed to download media {media_id}: {e}")
        raise MediaProcessingError(f"Download failed: {e}")


async def get_media_download_url(media_id: str) -> tuple[str, str]:
    """
    Get the download URL and MIME type for a media ID from WhatsApp API.
    
    Args:
        media_id: WhatsApp media ID
        
    Returns:
        Tuple of (media_url, mime_type)
        
    Raises:
        MediaProcessingError: If API call fails
    """
    url = f"https://graph.facebook.com/v20.0/{media_id}"
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            media_url = data.get("url")
            mime_type = data.get("mime_type", "image/jpeg")  # Default to jpeg if not provided
            
            if not media_url:
                raise MediaProcessingError("No URL in media response")
            
            logger.debug(f"Media {media_id}: mime_type={mime_type}")
            return media_url, mime_type
    except Exception as e:
        logger.error(f"Failed to get media URL for {media_id}: {e}")
        raise MediaProcessingError(f"Failed to get media URL: {e}")


async def upload_media_to_whatsapp(file_path: str, mime_type: Optional[str] = None) -> str:
    """
    Upload media file to WhatsApp and return media ID.
    
    Args:
        file_path: Path to file to upload
        mime_type: Optional MIME type (auto-detected if not provided)
        
    Returns:
        WhatsApp media ID
        
    Raises:
        MediaProcessingError: If upload fails
    """
    # Auto-detect MIME type if not provided
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            # Default based on extension
            if file_path.lower().endswith(('.jpg', '.jpeg')):
                mime_type = 'image/jpeg'
            elif file_path.lower().endswith('.png'):
                mime_type = 'image/png'
            else:
                mime_type = 'application/octet-stream'
    
    logger.info(f"Uploading media: {file_path} (type: {mime_type})")
    
    # Verify file exists
    if not os.path.exists(file_path):
        raise MediaProcessingError(f"File not found: {file_path}")
    
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
                
                if not media_id:
                    raise MediaProcessingError("No media ID in upload response")
                
                logger.info(f"Media uploaded successfully: {media_id}")
                return media_id
                
    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to upload media: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            logger.error(f"Response: {e.response.text}")
        raise MediaProcessingError(f"Upload failed: {e}")


def validate_media_path(path: str) -> bool:
    """
    Validate that a media path is real and accessible.
    
    Args:
        path: Path to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not path:
        return False
    
    # Check if it's a URL
    if path.startswith("http://") or path.startswith("https://"):
        return True
    
    # Check if file exists
    if os.path.exists(path) and os.path.isfile(path):
        return True
    
    logger.warning(f"Invalid media path: {path}")
    return False


def extract_image_url_from_text(text: str) -> Tuple[str, Optional[str]]:
    """
    Extract IMAGE_URL: from AI response text.
    Handles both simple and markdown formats:
    - Simple: IMAGE_URL:images/file.jpg
    - Markdown: ![IMAGE_URL:images/file.jpg](IMAGE_URL:images/file.jpg)
    
    Args:
        text: AI response text that may contain IMAGE_URL:path
        
    Returns:
        Tuple of (caption_text, image_path) or (original_text, None)
    """
    if "IMAGE_URL:" not in text:
        return text, None
    
    # Try to extract from markdown format first: ![...](IMAGE_URL:path)
    markdown_pattern = r'!\[(?:IMAGE_URL:)?([^\]]+)\]\(IMAGE_URL:([^\)]+)\)'
    markdown_match = re.search(markdown_pattern, text)
    
    if markdown_match:
        # Found markdown format
        image_path = markdown_match.group(2).strip()
        # Remove the entire markdown image from the caption
        caption = re.sub(markdown_pattern, '', text).strip()
        logger.info(f"Extracted image path from markdown: '{image_path}'")
    else:
        # Fall back to simple format: IMAGE_URL:path
        parts = text.split("IMAGE_URL:", 1)
        caption = parts[0].strip()
        
        # Extract path and clean it (remove trailing punctuation)
        raw_path = parts[1].strip().split()[0] if parts[1].strip() else ""
        image_path = re.sub(r'[)\]}>"\'\s]+$', '', raw_path)
        logger.info(f"Extracted image path from text: '{image_path}'")
    
    # Validate the path
    if not validate_media_path(image_path):
        logger.warning(f"Extracted path is invalid: '{image_path}'")
        return caption or text, None
    
    return caption, image_path


async def process_incoming_media(media_id: str) -> tuple[bytes, str]:
    """
    Process incoming media: get URL, MIME type, and download.
    
    Args:
        media_id: WhatsApp media ID
        
    Returns:
        Tuple of (media_binary_data, mime_type)
        
    Raises:
        MediaProcessingError: If processing fails
    """
    media_url, mime_type = await get_media_download_url(media_id)
    media_data = await download_media_from_url(media_url, media_id)
    return media_data, mime_type

