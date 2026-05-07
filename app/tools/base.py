"""Base tool class with plan-aware gating."""
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.models.user import User
from app.tools.context import get_current_phone, get_current_user_id
from app.core.plans import tier_rank, tool_allowed


class BaseTool(ABC):
    """Common interface every built-in tool implements."""

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
        """Tool is exposed to a user only if enabled, the user's tier meets the
        minimum, AND the tool is whitelisted in that tier's plan config."""
        if not self.enabled:
            return False
        user_tier = user.subscription_tier or "free"
        if tier_rank(user_tier) < tier_rank(self.min_tier):
            return False
        return tool_allowed(user_tier, self.name)

    @abstractmethod
    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        """Run the tool and return a string for the model (or None on failure)."""
        ...

    def to_pydanticai_tool(self):
        """Wrap as a PydanticAI tool. Forwards the current phone via kwargs."""

        async def _tool(text: str) -> str:
            phone = get_current_phone()
            user_id = get_current_user_id()
            result = await self.process(text=text, phone=phone, user_id=user_id)
            return result or "The tool didn't return any content."

        _tool.__name__ = self.name
        _tool.__doc__ = f"{self.description}\n\n{self.capabilities}"
        return _tool
