"""Safe arithmetic calculator (AST-based, no `eval`)."""
import ast
import operator
from typing import Any, Optional

from app.tools.base import BaseTool


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


class CalculatorTool(BaseTool):
    """Evaluate arithmetic expressions safely."""

    def __init__(self, enabled: bool = True):
        super().__init__(
            name="calculator",
            description="Evaluate a basic arithmetic expression.",
            capabilities=(
                "Supports +, -, *, /, //, %, ** and parentheses on numbers. "
                "Pass the raw expression as text (e.g. '2 + 2 * 3')."
            ),
            enabled=enabled,
            min_tier="free",
        )

    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        expr = (text or "").strip()
        if not expr:
            return "No expression provided."
        try:
            tree = ast.parse(expr, mode="eval")
            value = _safe_eval(tree)
        except ZeroDivisionError:
            return "Error: division by zero."
        except (SyntaxError, ValueError):
            return "I couldn't parse that expression. Try something like '2 + 2 * 3'."
        return f"The result is: {value}"
