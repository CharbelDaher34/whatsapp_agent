"""Gmail search tool — read-only.

Requires the user to have completed the Google OAuth flow. Looks up the
Gmail integration record, refreshes the access token if needed, and queries
the Gmail REST API. Returns up to 5 messages summarised as
``date | from | subject | snippet``.
"""
from typing import Any, Optional

import httpx

from app.core.logging import logger
from app.db.session import get_session
from app.services.integration_service import (
    get_active,
    get_fresh_google_access_token,
)
from app.tools.base import BaseTool


_GMAIL_LIST_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
_GMAIL_GET_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/{id}"
_MAX_RESULTS = 5


def _header(headers: list[dict], name: str) -> str:
    name_lower = name.lower()
    for h in headers:
        if (h.get("name") or "").lower() == name_lower:
            return h.get("value") or ""
    return ""


class GmailSearchTool(BaseTool):
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="gmail_search",
            description="Search the user's Gmail for messages matching a query.",
            capabilities=(
                "Pass a Gmail search query (e.g. 'from:alice subject:invoice newer_than:7d'). "
                "Returns up to 5 messages with date / from / subject / snippet. "
                "Requires the user to have connected Gmail in the dashboard."
            ),
            enabled=enabled,
            min_tier="pro",
        )

    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        user_id = kwargs.get("user_id")
        if not user_id:
            return "gmail_search needs a logged-in user context."

        query = (text or "").strip()
        if not query:
            return "gmail_search requires a query, e.g. 'from:boss@example.com newer_than:7d'."

        async with get_session() as session:
            integration = await get_active(session, user_id, "google")
            if not integration:
                return (
                    "Gmail isn't connected. Ask the user to open their dashboard "
                    "and click 'Connect Gmail', then try again."
                )
            token = await get_fresh_google_access_token(session, user_id)
            await session.commit()

        if not token:
            return (
                "Gmail authentication has expired. Ask the user to reconnect Gmail "
                "in the dashboard."
            )

        headers = {"Authorization": f"Bearer {token}"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                listing = await client.get(
                    _GMAIL_LIST_URL,
                    params={"q": query, "maxResults": _MAX_RESULTS},
                    headers=headers,
                )
                listing.raise_for_status()
                ids = [m["id"] for m in (listing.json().get("messages") or [])][:_MAX_RESULTS]
                if not ids:
                    return f"No Gmail messages match '{query}'."

                lines: list[str] = []
                for mid in ids:
                    detail = await client.get(
                        _GMAIL_GET_URL.format(id=mid),
                        params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
                        headers=headers,
                    )
                    detail.raise_for_status()
                    msg = detail.json()
                    headers_list = (msg.get("payload") or {}).get("headers") or []
                    snippet = (msg.get("snippet") or "").strip()[:140]
                    lines.append(
                        " | ".join([
                            _header(headers_list, "Date")[:25],
                            _header(headers_list, "From")[:40],
                            _header(headers_list, "Subject")[:60],
                            snippet,
                        ])
                    )
        except httpx.HTTPStatusError as e:
            logger.error(f"Gmail API error {e.response.status_code}: {e.response.text[:200]}")
            return f"Gmail returned an error (HTTP {e.response.status_code}). Try reconnecting Gmail."
        except Exception as e:
            logger.error(f"Gmail search failed: {e}")
            return "Gmail search failed. Try again later."

        return "Recent matching messages:\n" + "\n".join(f"• {l}" for l in lines)
