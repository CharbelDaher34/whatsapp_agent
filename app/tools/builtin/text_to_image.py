"""Text to image generation tool using Gemini API (Nano Banana)."""
from typing import Optional, Any
from app.tools.base import BaseTool
from app.core.config import settings
from app.core.logging import logger
import httpx
import base64
import json
import os
import re
from datetime import datetime

class TextToImageTool(BaseTool):
    """Generate images from text descriptions using Gemini Nano Banana."""
    
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="text_to_image",
            description="Generate images from text descriptions using Gemini",
            capabilities=(
                "Creates high-quality images using Gemini 2.5 Flash Image (Nano Banana). "
                "Supports detailed descriptions and various aspect ratios."
            ),
            enabled=enabled,
            min_tier="free",
        )
    
    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        """Generate an image from text prompt."""
        try:
            prompt = text.strip()
            if not prompt:
                return "Please provide a description of the image you want to generate."
            
            # Use Gemini API Key (reusing GOOGLE_CLOUD_API_KEY env var for simplicity)
            if not settings.GOOGLE_CLOUD_API_KEY:
                logger.error("GOOGLE_CLOUD_API_KEY not configured")
                return "Image generation is not configured. Please contact admin."
            
            image_path = await self._generate_with_gemini(prompt)
            
            if image_path:
                # Return in format that whatsapp_service can parse
                # The service looks for "IMAGE_URL:" to send the image
                # Caption will be the text before IMAGE_URL:
                return f"IMAGE_URL:{image_path}"
            else:
                return "Sorry, I couldn't generate the image. Please try again."
                
        except Exception as e:
            logger.error(f"Error in text_to_image tool: {e}")
            return "An error occurred while generating the image."
    
    async def _generate_with_gemini(self, prompt: str) -> Optional[str]:
        """Generate image using Gemini 2.5 Flash Image API and return local file path."""
        try:
            logger.info(f"🎨 Calling Gemini API to generate image: {prompt[:50]}...")
            
            # Gemini API endpoint - use gemini-2.5-flash-image model
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent"
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt}
                    ]
                }]
            }
            
            # Use x-goog-api-key header as per documentation
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": settings.GOOGLE_CLOUD_API_KEY
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=60.0)
                
                logger.info(f"📨 Gemini API response: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    candidates = result.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            if "inlineData" in part:
                                image_base64 = part["inlineData"]["data"]
                                file_path = await self._save_image(image_base64, prompt)
                                logger.info(f"✅ Image saved to: {file_path}")
                                return file_path
                            elif "text" in part:
                                logger.info(f"Gemini text response: {part['text'][:100]}")
                        logger.warning("No image data in response")
                    else:
                        logger.warning(f"No candidates in response: {result}")
                else:
                    logger.error(f"❌ Gemini API error: {response.status_code} - {response.text[:500]}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error calling Gemini API: {e}", exc_info=True)
            return None
    
    async def _save_image(self, image_base64: str, prompt: str) -> str:
        """Save generated image and return file path."""
    
        # Ensure images directory exists
        os.makedirs("images", exist_ok=True)
    
        # Sanitize filename (letters, numbers, dash, underscore)
        safe_prompt = re.sub(r"[^a-zA-Z0-9-_ ]", "", prompt)[:50].strip().replace(" ", "_")
    
        # Use timestamp to avoid overwriting files
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"{safe_prompt}_{timestamp}.jpg"
    
        filepath = os.path.join("images", filename)
    
        # Decode Base64 image safely
        try:
            image_bytes = base64.b64decode(image_base64)
        except Exception:
            raise ValueError("Invalid base64 image data")
    
        # Save image
        with open(filepath, "wb") as f:
            f.write(image_bytes)
    
        return filepath
