"""Tools that let the assistant ask the user a structured follow-up question.

Two flavours:
- ``ask_buttons``: WhatsApp interactive buttons (max 3, ≤20 chars each).
- ``ask_list``: WhatsApp interactive list (up to 10 rows in one section).

Both tools send the prompt directly via the WhatsApp Cloud API. The model
should then end its reply with the sentinel ``[NO_TEXT_REPLY]`` so the
response builder doesn't double-message the user.

Tool input is a single JSON-encoded string (PydanticAI tools take ``text``):

ask_buttons:
    {"prompt": "Which size?", "options": ["Small", "Medium", "Large"]}

ask_list:
    {
      "prompt": "Pick a topping",
      "button": "Choose",
      "items": [
        {"id": "pepperoni", "title": "Pepperoni", "description": "Classic"},
        {"id": "veggie", "title": "Veggie"}
      ]
    }
"""
import json
from typing import Any, List, Optional

from app.tools.base import BaseTool
from app.services.interactive_messages import send_button_message, send_list_message
from app.core.logging import logger


_NO_REPLY = "[NO_TEXT_REPLY]"


def _parse_json(text: str) -> Optional[dict]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


class AskButtonsTool(BaseTool):
    """Send the user a button question (max 3 buttons)."""

    def __init__(self, enabled: bool = True):
        super().__init__(
            name="ask_buttons",
            description="Ask the user a question with up to 3 quick-reply buttons.",
            capabilities=(
                "Use when you need a quick choice from 2-3 options. "
                'Input MUST be JSON: {"prompt": "<question>", "options": ["A", "B", "C"]}. '
                "After calling this, end your reply with [NO_TEXT_REPLY] so the user only sees the buttons."
            ),
            enabled=enabled,
            min_tier="free",
        )

    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        phone = kwargs.get("phone")
        if not phone:
            return "ask_buttons failed: no recipient phone in context."
        data = _parse_json(text)
        if not data or not isinstance(data, dict):
            return (
                "ask_buttons input must be JSON like "
                '{"prompt": "Which size?", "options": ["S", "M", "L"]}.'
            )
        prompt = (data.get("prompt") or "").strip()
        options: List[Any] = data.get("options") or []
        if not prompt or not options:
            return "ask_buttons requires both 'prompt' and 'options'."

        buttons = []
        for i, opt in enumerate(options[:3]):
            if isinstance(opt, dict):
                btn_id = str(opt.get("id") or f"opt_{i}")
                title = str(opt.get("title") or opt.get("label") or btn_id)
            else:
                btn_id = f"opt_{i}"
                title = str(opt)
            buttons.append({"id": btn_id[:200], "title": title[:20]})

        ok = await send_button_message(to=phone, body_text=prompt[:1024], buttons=buttons)
        if not ok:
            return "ask_buttons failed to send. Continue the conversation in plain text."
        logger.info(f"📨 Sent button question to {phone}: {[b['title'] for b in buttons]}")
        return f"BUTTONS_SENT to user with options: {', '.join(b['title'] for b in buttons)}. Reply with only {_NO_REPLY}."


class AskListTool(BaseTool):
    """Send the user a single-section interactive list (up to 10 items)."""

    def __init__(self, enabled: bool = True):
        super().__init__(
            name="ask_list",
            description="Ask the user to pick from a list of up to 10 items.",
            capabilities=(
                "Use when there are more than 3 options or items need a description. "
                "Input MUST be JSON: "
                '{"prompt": "<question>", "button": "<menu label>", '
                '"items": [{"id": "x", "title": "X", "description": "..."}]}. '
                "After calling this, end your reply with [NO_TEXT_REPLY] so the user only sees the list."
            ),
            enabled=enabled,
            min_tier="free",
        )

    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        phone = kwargs.get("phone")
        if not phone:
            return "ask_list failed: no recipient phone in context."
        data = _parse_json(text)
        if not data or not isinstance(data, dict):
            return (
                "ask_list input must be JSON like "
                '{"prompt": "Pick one", "button": "Choose", '
                '"items": [{"id": "a", "title": "A"}]}.'
            )
        prompt = (data.get("prompt") or "").strip()
        button_label = (data.get("button") or "Choose")[:20]
        items_raw = data.get("items") or []
        if not prompt or not items_raw:
            return "ask_list requires 'prompt' and a non-empty 'items' array."

        rows = []
        for i, item in enumerate(items_raw[:10]):
            if isinstance(item, dict):
                row_id = str(item.get("id") or f"item_{i}")
                title = str(item.get("title") or row_id)
                desc = str(item.get("description") or "")
            else:
                row_id = f"item_{i}"
                title = str(item)
                desc = ""
            row = {"id": row_id[:200], "title": title[:24]}
            if desc:
                row["description"] = desc[:72]
            rows.append(row)

        sections = [{"title": (data.get("section_title") or "Options")[:24], "rows": rows}]
        ok = await send_list_message(
            to=phone,
            body_text=prompt[:1024],
            button_text=button_label,
            sections=sections,
        )
        if not ok:
            return "ask_list failed to send. Continue the conversation in plain text."
        logger.info(f"📨 Sent list question to {phone}: {[r['title'] for r in rows]}")
        return f"LIST_SENT to user with {len(rows)} options. Reply with only {_NO_REPLY}."


class EchoTool(BaseTool):
    """Tiny diagnostic tool replacing the old MyTool placeholder."""

    def __init__(self, enabled: bool = True):
        super().__init__(
            name="echo",
            description="Echo a string back. Useful only for diagnostics.",
            capabilities="Returns the input prefixed with 'Echo:'.",
            enabled=enabled,
            min_tier="free",
        )

    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        return f"Echo: {text}"
