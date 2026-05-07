"""Central tool registry with plan-aware filtering."""
from typing import Dict, List

from app.models.user import User
from app.tools.base import BaseTool
from app.tools.builtin.ask_user import AskButtonsTool, AskListTool, EchoTool
from app.tools.builtin.calculator import CalculatorTool
from app.tools.builtin.text_to_image import TextToImageTool
from app.tools.builtin.image_to_image import ImageToImageTool


_TOOL_INSTANCES: Dict[str, BaseTool] = {}


def init_tools() -> None:
    """Register every built-in tool. Idempotent — safe to call repeatedly."""
    _TOOL_INSTANCES.clear()
    for tool in [
        EchoTool(),
        CalculatorTool(),
        AskButtonsTool(),
        AskListTool(),
        TextToImageTool(),
        ImageToImageTool(),
    ]:
        _TOOL_INSTANCES[tool.name] = tool


def get_all_tools() -> Dict[str, BaseTool]:
    return _TOOL_INSTANCES


def get_tools_for_user(user: User) -> List[BaseTool]:
    """Return only tools the user is eligible for under their plan."""
    return [t for t in _TOOL_INSTANCES.values() if t.is_valid_for_user(user)]
