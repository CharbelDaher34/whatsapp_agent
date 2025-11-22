import asyncio
from unittest.mock import MagicMock, patch
from app.services.whatsapp_service import handle_incoming_webhook
from app.tools.image_generation import GenerateImageTool

# Mock payload for image message
IMAGE_PAYLOAD = {
    "entry": [{
        "changes": [{
            "value": {
                "messages": [{
                    "from": "1234567890",
                    "type": "image",
                    "image": {
                        "id": "media_123",
                        "caption": "What is this?"
                    }
                }]
            }
        }]
    }]
}

# Mock payload for text message requesting image
TEXT_PAYLOAD = {
    "entry": [{
        "changes": [{
            "value": {
                "messages": [{
                    "from": "1234567890",
                    "type": "text",
                    "text": {
                        "body": "Generate an image of a futuristic city"
                    }
                }]
            }
        }]
    }]
}

async def test_image_input():
    print("\n--- Testing Image Input ---")
    
    with patch("app.services.whatsapp_service.get_media_url") as mock_get_url, \
         patch("app.services.whatsapp_service.generate_reply") as mock_reply, \
         patch("app.services.whatsapp_service.send_whatsapp_text") as mock_send:
        
        mock_get_url.return_value = "http://example.com/image.jpg"
        mock_reply.return_value = "I see a cat in this image."
        
        await handle_incoming_webhook(IMAGE_PAYLOAD)
        
        mock_get_url.assert_called_once_with("media_123")
        mock_reply.assert_called_once()
        # Check if image_url was passed to generate_reply
        args, kwargs = mock_reply.call_args
        assert kwargs.get("image_url") == "http://example.com/image.jpg"
        
        mock_send.assert_called_with(to="1234567890", message="I see a cat in this image.")
        print("✅ Image input handled correctly")

async def test_image_generation():
    print("\n--- Testing Image Generation ---")
    
    with patch("app.services.whatsapp_service.generate_reply") as mock_reply, \
         patch("app.services.whatsapp_service.send_whatsapp_image") as mock_send_img, \
         patch("app.services.whatsapp_service.send_whatsapp_text") as mock_send_text, \
         patch("app.services.whatsapp_service.upload_media") as mock_upload:
        
        # Simulate agent returning a local file path with text
        mock_reply.return_value = "Here is your futuristic city! IMAGE_URL:images/gen_123.jpg"
        mock_upload.return_value = "media_id_999"
        
        await handle_incoming_webhook(TEXT_PAYLOAD)
        
        # Verify text message was NOT sent separately
        mock_send_text.assert_not_called()
        
        # Verify image was uploaded and sent with caption in ONE message
        mock_upload.assert_called_with("images/gen_123.jpg")
        mock_send_img.assert_called_with(
            to="1234567890", 
            image_url=None, 
            media_id="media_id_999",
            caption="Here is your futuristic city!"
        )
        print("✅ Image generation output handled correctly (Single message with caption)")

async def test_video_input():
    print("\n--- Testing Video Input ---")
    
    VIDEO_PAYLOAD = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "1234567890",
                        "type": "video",
                        "video": {
                            "id": "video_456",
                            "caption": "Check out this video!"
                        }
                    }]
                }
            }]
        }]
    }
    
    with patch("app.services.whatsapp_service.get_media_url") as mock_get_url, \
         patch("app.services.whatsapp_service.generate_reply") as mock_reply, \
         patch("app.services.whatsapp_service.send_whatsapp_text") as mock_send:
        
        mock_get_url.return_value = "http://example.com/video.mp4"
        mock_reply.return_value = "Nice video! I can see it."
        
        await handle_incoming_webhook(VIDEO_PAYLOAD)
        
        mock_get_url.assert_called_once_with("video_456")
        mock_reply.assert_called_once()
        mock_send.assert_called_with(to="1234567890", message="Nice video! I can see it.")
        print("✅ Video input handled correctly")

if __name__ == "__main__":
    asyncio.run(test_image_input())
    asyncio.run(test_image_generation())
    asyncio.run(test_video_input())
