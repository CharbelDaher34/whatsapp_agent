"""Image generation tool using OpenAI DALL-E 3."""
from typing import Optional, Any
from app.tools.base import BaseTool
from app.core.config import settings
from app.core.logging import logger
from openai import AsyncOpenAI
import os
import httpx
from datetime import datetime
import re

class GenerateImageTool(BaseTool):
    """Generate images from text descriptions using OpenAI DALL-E 3."""
    
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="generate_image",
            description="Generate images from text descriptions using DALL-E 3",
            capabilities=(
                "Creates high-quality images using OpenAI DALL-E 3. "
                "Supports detailed descriptions."
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
            
            logger.info(f"🎨 GenerateImageTool called with prompt: '{prompt}'")
            
            if not settings.OPENAI_API_KEY:
                logger.error("OPENAI_API_KEY not configured")
                return "Image generation is not configured. Please contact admin."
            
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            
            logger.info("🎨 Sending request to OpenAI DALL-E 3...")
            response = await client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            
            image_url = response.data[0].url
            logger.info(f"🎨 Image generated successfully. URL: {image_url}")
            
            # Download and save the image locally so we can serve it
            local_path = await self._save_image_from_url(image_url, prompt)
            
            if local_path:
                # In a real app, you'd return a public URL. 
                # For now, we'll return the local path which the whatsapp client will handle
                # or we could return the OpenAI URL but it expires.
                # Let's return the OpenAI URL for simplicity if it works, 
                # but saving it is better for persistence.
                # The whatsapp client needs a public URL or we need to upload it to WhatsApp.
                # For this implementation, let's assume we send the OpenAI URL directly 
                # or we serve the local file via a static mount (not set up yet).
                # Let's return the OpenAI URL for now, but also save it.
                return f"IMAGE_URL:{image_url}" 
            
            return "Sorry, I generated the image but couldn't save it."
                
        except Exception as e:
            logger.error(f"Error in generate_image tool: {e}")
            return f"An error occurred while generating the image: {str(e)}"
    
    async def _save_image_from_url(self, url: str, prompt: str) -> Optional[str]:
        """Download image from URL and save locally."""
        try:
            # Ensure images directory exists
            os.makedirs("images", exist_ok=True)
            
            # Sanitize filename
            safe_prompt = re.sub(r"[^a-zA-Z0-9-_ ]", "", prompt)[:50].strip().replace(" ", "_")
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            filename = f"{safe_prompt}_{timestamp}.png"
            filepath = os.path.join("images", filename)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                if response.status_code == 200:
                    with open(filepath, "wb") as f:
                        f.write(response.content)
                    return filepath
            return None
        except Exception as e:
            logger.error(f"Error saving image: {e}")
            return None
