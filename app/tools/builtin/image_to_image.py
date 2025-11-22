"""Image to image transformation tool using Gemini API."""
import os
from typing import Optional, Any
from app.tools.base import BaseTool
from app.core.config import settings
from app.core.logging import logger
import httpx
import base64
import json


class ImageToImageTool(BaseTool):
    """Transform images based on text descriptions using Gemini Nano Banana."""
    
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="image_to_image",
            description="Transform or edit existing images using Gemini",
            capabilities=(
                "Transforms existing images based on text instructions. "
                "Can apply styles, edit specific parts, or create variations."
            ),
            enabled=enabled,
            min_tier="pro",
        )
    
    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        """Transform an image based on text instructions."""
        try:
            instruction = text.strip()
            image_url = kwargs.get('image_url', None)
            
            if not instruction:
                return "Please provide transformation instructions."
            
            if not image_url:
                return "Please provide an image to transform first."
            
            if not settings.GOOGLE_CLOUD_API_KEY:
                logger.error("GOOGLE_CLOUD_API_KEY not configured")
                return "Image transformation is not configured. Please contact admin."
            
            result_url = await self._transform_image(image_url, instruction)
            
            if result_url:
                return f"🎨 Image transformed successfully!\n\n📸 View result: {result_url}\n\nInstruction: '{instruction}'"
            else:
                return "Sorry, I couldn't transform the image. Please try again."
                
        except Exception as e:
            logger.error(f"Error in image_to_image tool: {e}")
            return "An error occurred while transforming the image."
    
    async def _transform_image(self, image_url: str, instruction: str) -> Optional[str]:
        """Transform image using Gemini 2.5 Flash Image API."""
        try:
            # Fetch image
            image_base64 = await self._fetch_image_as_base64(image_url)
            if not image_base64:
                return None
            
            # Gemini API endpoint
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={settings.GOOGLE_CLOUD_API_KEY}"
            
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
                }],
                "generationConfig": {
                    "responseModalities": ["IMAGE"]
                }
            }
            
            headers = {"Content-Type": "application/json"}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=60.0)
                
                if response.status_code == 200:
                    result = response.json()
                    candidates = result.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            if "inlineData" in part:
                                result_base64 = part["inlineData"]["data"]
                                return await self._save_image(result_base64, instruction)
                
                logger.error(f"Gemini API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error transforming image: {e}")
            return None
    
    async def _fetch_image_as_base64(self, image_url: str) -> Optional[str]:
        """check if not url, try locql storage"""
        if not image_url.startswith("http"):
            image_path = os.path.join("images", image_url)
            if os.path.exists(image_path):
                with open(image_path, "rb") as f:
                    return base64.b64encode(f.read()).decode('utf-8')
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
        """Save generated image and return URL."""
        # Placeholder
        return f"[Transformed image: {prompt[:50]}...]"