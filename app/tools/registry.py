"""Tool registry for managing all available tools."""
from typing import Dict, List
from app.tools.base import BaseTool
from app.models.user import User
from app.tools.builtin.my_tool import MyTool
from app.tools.builtin.text_to_image import TextToImageTool
from app.tools.builtin.image_to_image import ImageToImageTool

# Global registry
_TOOL_INSTANCES: Dict[str, BaseTool] = {}


def init_tools():
    """
    Initialize and register all built-in tools.
    Call this once at application startup.
    """
    for tool in [
        MyTool(),
        # CalculatorTool(),
        TextToImageTool(),
        ImageToImageTool(),
    ]:
        _TOOL_INSTANCES[tool.name] = tool


def get_all_tools() -> Dict[str, BaseTool]:
    """Get all registered tools."""
    return _TOOL_INSTANCES


def get_tools_for_user(user: User) -> List[BaseTool]:
    """Get tools available for a specific user based on subscription tier."""
    return [t for t in _TOOL_INSTANCES.values() if t.is_valid_for_user(user)]


