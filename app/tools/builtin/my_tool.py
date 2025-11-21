"""Example tool implementation."""
from typing import Optional, Any
from app.tools.base import BaseTool


class MyTool(BaseTool):
    """Simple demo tool for testing."""
    
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="my_tool",
            description="Simple demo tool",
            capabilities=(
                "Takes user text and returns it with 'Processed:' prefix. "
                "This is a demonstration tool."
            ),
            enabled=enabled,
            min_tier="free",
        )
    
    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        """Process text by adding a prefix."""
        try:
            result = f"Processed: {text}"
            return result
        except Exception as e:
            print(f"Error in my_tool: {e}")
            return None


