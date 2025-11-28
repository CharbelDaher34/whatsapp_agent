"""Image to image transformation tool using Gemini API."""
import os
import re
from typing import Optional, Any
from datetime import datetime
from app.tools.base import BaseTool
from app.core.config import settings
from app.core.logging import logger
import httpx
import base64


class ImageToImageTool(BaseTool):
    """Transform images based on text descriptions using Gemini Nano Banana."""
    
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="image_to_image",
            description="Transform or edit the user's recently uploaded image using Gemini",
            capabilities=(
                "Transforms the user's most recently uploaded image based on text instructions. "
                "Can apply styles, edit specific parts, or create variations. "
                "The image is automatically retrieved - just provide the transformation instruction."
            ),
            enabled=enabled,
            min_tier="free",
        )
    
    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        """Transform an image based on text instructions."""
        try:
            instruction = text.strip()
            
            if not instruction:
                return "Please provide transformation instructions (e.g., 'make it cartoon style')."
            
            # Get the phone number from kwargs (passed by the tool wrapper)
            phone = kwargs.get('phone')
            
            # Get image path from Redis (deterministic - no reliance on AI)
            image_path = None
            if phone:
                from app.services.whatsapp.handlers.image_handler import get_user_current_image
                image_path = await get_user_current_image(phone)
                logger.info(f"📍 Retrieved image path from Redis for {phone}: {image_path}")
            
            # Fallback: check for embedded path in text (backwards compatibility)
            if not image_path and "[USER_IMAGE_PATH:" in instruction:
                match = re.search(r'\[USER_IMAGE_PATH:([^\]]+)\]', instruction)
                if match:
                    image_path = match.group(1)
                    instruction = re.sub(r'\[USER_IMAGE_PATH:[^\]]+\]', '', instruction).strip()
            
            if not image_path:
                return "No image found. Please send an image first, then ask me to transform it."
            
            if not settings.GOOGLE_CLOUD_API_KEY:
                logger.error("GOOGLE_CLOUD_API_KEY not configured")
                return "Image transformation is not configured. Please contact admin."
            
            logger.info(f"🎨 Transforming image: {image_path} with instruction: {instruction[:50]}...")
            result_path = await self._transform_image(image_path, instruction)
            
            if result_path:
                # Return in IMAGE_URL format so it gets sent to WhatsApp
                return f"IMAGE_URL:{result_path}"
            else:
                return "Sorry, I couldn't transform the image. Please try again."
                
        except Exception as e:
            logger.error(f"Error in image_to_image tool: {e}", exc_info=True)
            return "An error occurred while transforming the image."
    
    async def _transform_image(self, image_url: str, instruction: str) -> Optional[str]:
        """Transform image using Gemini 2.5 Flash Image API."""
        try:
            # Fetch image
            logger.info(f"📥 Loading image from: {image_url}")
            image_base64 = await self._fetch_image_as_base64(image_url)
            if not image_base64:
                logger.error(f"❌ Failed to load image from: {image_url}")
                return None
            
            logger.info(f"✅ Image loaded, base64 length: {len(image_base64)}")
            
            # Gemini API endpoint - use gemini-2.5-flash-image model
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent"
            
            # Payload format per documentation: text prompt + image in parts array
            payload = {
                "contents": [{
                    "parts": [
                        {"text": instruction},
                        {
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": image_base64
                            }
                        }
                    ]
                }]
            }
            
            # Use x-goog-api-key header as per documentation
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": settings.GOOGLE_CLOUD_API_KEY
            }
            
            logger.info(f"📤 Calling Gemini API for image transformation...")
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=60.0)
                
                logger.info(f"📨 Gemini API response status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    candidates = result.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        logger.info(f"Found {len(parts)} parts in response")
                        for part in parts:
                            if "inlineData" in part:
                                result_base64 = part["inlineData"]["data"]
                                logger.info(f"✅ Got transformed image, saving...")
                                return await self._save_image(result_base64, instruction)
                            elif "text" in part:
                                logger.info(f"Gemini text: {part['text'][:100]}")
                        logger.warning(f"⚠️ No inlineData found in response parts")
                    else:
                        logger.warning(f"⚠️ No candidates in response: {result}")
                else:
                    logger.error(f"❌ Gemini API error: {response.status_code} - {response.text[:500]}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error transforming image: {e}", exc_info=True)
            return None
    
    async def _fetch_image_as_base64(self, image_url: str) -> Optional[str]:
        """Load local image or fetch from URL and convert to base64."""
        if not image_url.startswith("http"):
            # It's a local path - use as-is if it already includes "images/"
            image_path = image_url if image_url.startswith("images/") else os.path.join("images", image_url)
            
            # Detailed debugging
            logger.info(f"🔍 Looking for local image at: {image_path}")
            logger.info(f"🔍 Current working directory: {os.getcwd()}")
            logger.info(f"🔍 Absolute path: {os.path.abspath(image_path)}")
            logger.info(f"🔍 Path exists: {os.path.exists(image_path)}")
            
            # List images directory
            if os.path.exists("images"):
                files = os.listdir("images")
                logger.info(f"🔍 Files in images/: {files[:5]}...")  # Show first 5
            else:
                logger.error("❌ images/ directory doesn't exist!")
            
            if os.path.exists(image_path):
                with open(image_path, "rb") as f:
                    image_data = f.read()
                    logger.info(f"✅ Loaded local image: {len(image_data)} bytes")
                    return base64.b64encode(image_data).decode('utf-8')
            else:
                logger.error(f"❌ Local image not found: {image_path}")
            return None
        """Fetch image from URL and convert to base64."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url, timeout=10.0)
                if response.status_code == 200:
                    return base64.b64encode(response.content).decode('utf-8')
            return None
        except Exception as e:
            logger.error(f"Error fetching image: {e}")
            return None
            
    async def _save_image(self, image_base64: str, prompt: str) -> str:
        """Save generated image and return file path."""
        # Ensure images directory exists
        os.makedirs("images", exist_ok=True)
    
        # Sanitize filename
        safe_prompt = re.sub(r"[^a-zA-Z0-9-_ ]", "", prompt)[:50].strip().replace(" ", "_")
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"transformed_{safe_prompt}_{timestamp}.jpg"
        filepath = os.path.join("images", filename)
    
        # Decode and save
        try:
            image_bytes = base64.b64decode(image_base64)
            with open(filepath, "wb") as f:
                f.write(image_bytes)
            return filepath
        except Exception as e:
            logger.error(f"Failed to save transformed image: {e}")
            raise