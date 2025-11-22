"""Test script for image generation tools."""
import asyncio
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.tools.builtin.text_to_image import TextToImageTool
from app.tools.builtin.image_to_image import ImageToImageTool
from app.core.config import settings
from app.core.logging import logger


async def test_text_to_image():
    """Test text-to-image generation."""
    print("\n" + "="*60)
    print("Testing Text-to-Image Tool")
    print("="*60)
    
    if not settings.GOOGLE_CLOUD_API_KEY:
        print("❌ ERROR: GOOGLE_CLOUD_API_KEY not set in .env file")
        return False
    
    tool = TextToImageTool(enabled=True)
    
    # Test prompt
    test_prompt = "A cute robot holding a banana in a futuristic city"
    print(f"\n📝 Test prompt: '{test_prompt}'")
    print("⏳ Generating image...")
    
    try:
        result = await tool.process(test_prompt)
        print(f"\n✅ Result:\n{result}")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Text-to-image test failed")
        return False


async def test_image_to_image():
    """Test image-to-image transformation."""
    print("\n" + "="*60)
    print("Testing Image-to-Image Tool")
    print("="*60)
    
    if not settings.GOOGLE_CLOUD_API_KEY:
        print("❌ ERROR: GOOGLE_CLOUD_API_KEY not set in .env file")
        return False
    
    tool = ImageToImageTool(enabled=True)
    
    # Test with a sample image URL (you can replace this)
    test_image_url = "https://picsum.photos/512/512"  # Random test image
    test_image_url = "images/A_cute_robot_holding_a_banana_in_a_futuristic_city_20251121225359.jpg"
    test_instruction = "Make it look like a painting in the style of Van Gogh"
    
    print(f"\n📸 Test image URL: {test_image_url}")
    print(f"📝 Transformation instruction: '{test_instruction}'")
    print("⏳ Transforming image...")
    
    try:
        result = await tool.process(
            test_instruction,
            image_url=test_image_url
        )
        print(f"\n✅ Result:\n{result}")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Image-to-image test failed")
        return False


async def main():
    """Run all tests."""
    print("\n🧪 Image Generation Tools Test Suite")
    print("="*60)
    
    # Check configuration
    print("\n📋 Configuration Check:")
    print(f"   GOOGLE_CLOUD_API_KEY: {'✅ Set' if settings.GOOGLE_CLOUD_API_KEY else '❌ Not set'}")
    
    if not settings.GOOGLE_CLOUD_API_KEY:
        print("\n⚠️  Please set GOOGLE_CLOUD_API_KEY in your .env file")
        print("   Get your API key from: https://aistudio.google.com/")
        return
    
    # Run tests
    results = []
    
    # Test 1: Text to Image
    # results.append(await test_text_to_image())
    
    # Test 2: Image to Image
    results.append(await test_image_to_image())
    
    # Summary
    print("\n" + "="*60)
    print("📊 Test Summary")
    print("="*60)
    print(f"   Text-to-Image: {'✅ PASSED' if results[0] else '❌ FAILED'}")
    print(f"   Image-to-Image: {'✅ PASSED' if results[1] else '❌ FAILED'}")
    
    if all(results):
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")


if __name__ == "__main__":
    asyncio.run(main())
