"""Base tool class for all tools."""
from abc import ABC, abstractmethod
from typing import Optional, Any
from app.models.user import User


class BaseTool(ABC):
    """Base class for all tools with subscription validation."""
    
    def __init__(
        self,
        name: str,
        description: str,
        capabilities: str,
        enabled: bool = True,
        min_tier: str = "free",
    ):
        self.name = name
        self.description = description
        self.capabilities = capabilities
        self.enabled = enabled
        self.min_tier = min_tier
    
    def is_valid_for_user(self, user: User) -> bool:
        """
        Check if user is eligible to use this tool.
        Checks subscription tier and enabled status.
        """
        if not self.enabled:
            return False
        
        tier_order = {"free": 0, "plus": 1, "pro": 2}
        user_tier = user.subscription_tier or "free"
        return tier_order.get(user_tier, 0) >= tier_order.get(self.min_tier, 0)
    
    @abstractmethod
    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        """Process the input and return a string result (or None on failure)."""
        ...
    
    def to_pydanticai_tool(self):
        """
        Wrap this tool as a callable for PydanticAI.
        Returns a function that can be used as a PydanticAI tool.
        """
        async def _tool(text: str) -> str:
            result = await self.process(text=text)
            return result or "The tool didn't return any content."
        
        _tool.__name__ = self.name
        _tool.__doc__ = f"{self.description}\n\n{self.capabilities}"
        return _tool


