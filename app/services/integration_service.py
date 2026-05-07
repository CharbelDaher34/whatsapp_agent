"""CRUD layer for the ``integration`` table.

Handles:
- Storing access/refresh tokens (encrypted via ``app.web.crypto``).
- Looking up an active integration for a user/provider.
- Listing all integrations for a user (for the dashboard).
- Refreshing a Google access token when it's about to expire.
"""
from datetime import datetime, timedelta
from typing import List, Optional

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.integration import Integration
from app.web.crypto import decrypt_token, encrypt_token


_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


async def get_active(
    session: AsyncSession, user_id: int, provider: str,
) -> Optional[Integration]:
    """Return the active integration for ``(user_id, provider)`` or None."""
    stmt = select(Integration).where(
        Integration.user_id == user_id,
        Integration.provider == provider,
        Integration.status == "active",
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_for_user(session: AsyncSession, user_id: int) -> List[Integration]:
    stmt = select(Integration).where(Integration.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def upsert_google(
    session: AsyncSession,
    user_id: int,
    *,
    access_token: str,
    refresh_token: Optional[str],
    expires_in: Optional[int],
    scope: Optional[str],
    account_email: Optional[str],
) -> Integration:
    """Create-or-update the Google integration for ``user_id``."""
    expires_at = (
        datetime.utcnow() + timedelta(seconds=int(expires_in))
        if expires_in else None
    )
    existing = await get_active(session, user_id, "google")
    if existing is None:
        # also check inactive rows so we re-activate instead of duplicating
        stmt = select(Integration).where(
            Integration.user_id == user_id, Integration.provider == "google",
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()

    if existing:
        existing.access_token_enc = encrypt_token(access_token)
        if refresh_token:
            existing.refresh_token_enc = encrypt_token(refresh_token)
        existing.expires_at = expires_at
        existing.scope = scope
        existing.account_email = account_email or existing.account_email
        existing.status = "active"
        existing.updated_at = datetime.utcnow()
        session.add(existing)
        await session.flush()
        return existing

    row = Integration(
        user_id=user_id,
        provider="google",
        account_email=account_email,
        scope=scope,
        access_token_enc=encrypt_token(access_token),
        refresh_token_enc=encrypt_token(refresh_token) if refresh_token else None,
        expires_at=expires_at,
        status="active",
    )
    session.add(row)
    await session.flush()
    return row


async def revoke(session: AsyncSession, user_id: int, provider: str) -> int:
    result = await session.execute(
        delete(Integration).where(
            Integration.user_id == user_id, Integration.provider == provider,
        )
    )
    return result.rowcount or 0


async def get_fresh_google_access_token(
    session: AsyncSession, user_id: int,
) -> Optional[str]:
    """Return a valid Google access token, refreshing it if it's close to expiry.

    Returns ``None`` when the integration is missing or the refresh fails.
    """
    integration = await get_active(session, user_id, "google")
    if not integration:
        return None

    access = decrypt_token(integration.access_token_enc)
    if access and (
        not integration.expires_at
        or integration.expires_at > datetime.utcnow() + timedelta(seconds=60)
    ):
        return access

    refresh = decrypt_token(integration.refresh_token_enc)
    if not refresh or not (settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET):
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                    "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                    "refresh_token": refresh,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as e:
        logger.error(f"Google token refresh failed for user {user_id}: {e}")
        integration.status = "error"
        session.add(integration)
        await session.flush()
        return None

    new_access = payload.get("access_token")
    if not new_access:
        return None
    integration.access_token_enc = encrypt_token(new_access)
    expires_in = payload.get("expires_in")
    integration.expires_at = (
        datetime.utcnow() + timedelta(seconds=int(expires_in))
        if expires_in else None
    )
    integration.updated_at = datetime.utcnow()
    session.add(integration)
    await session.flush()
    return new_access
