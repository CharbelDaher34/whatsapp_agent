"""Calculator tool for basic math operations."""
from typing import Optional, Any
from app.tools.base import BaseTool
import re


class CalculatorTool(BaseTool):
    """Calculator tool for basic math operations."""
    
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="calculator",
            description="Perform basic math calculations",
            capabilities=(
                "Can evaluate mathematical expressions like '2 + 2', '10 * 5', "
                "'100 / 4', etc. Supports +, -, *, /, (, ), and numbers."
            ),
            enabled=enabled,
            min_tier="free",
        )
    
    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        """Evaluate a math expression safely."""
        try:
            # Remove all non-math characters for safety
            safe_text = re.sub(r'[^0-9+\-*/().\s]', '', text)
            if not safe_text:
                return "No valid mathematical expression found."
            
            result = eval(safe_text)
            return f"The result is: {result}"
        except ZeroDivisionError:
            return "Error: Division by zero."
        except Exception as e:
            return f"Error calculating: {str(e)}"


