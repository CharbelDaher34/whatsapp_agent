"""User-facing integration endpoints (Google OAuth + revoke)."""
import secrets
from typing import Optional
from urllib.parse import urlencode

import httpx
import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.db.session import get_session
from app.services.integration_service import revoke, upsert_google
from app.web.auth import require_user


router = APIRouter(prefix="/integrations", tags=["integrations"])


_GMAIL_SCOPES = " ".join([
    "openid", "email", "profile",
    "https://www.googleapis.com/auth/gmail.readonly",
])


def _redirect_uri() -> str:
    if settings.GOOGLE_OAUTH_REDIRECT_URI:
        return settings.GOOGLE_OAUTH_REDIRECT_URI
    return f"{settings.WEB_BASE_URL.rstrip('/')}/integrations/google/callback"


def _state_key(state: str) -> str:
    return f"oauth_state:{state}"


async def _redis() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


@router.get("/google/connect")
async def google_connect(claims: dict = Depends(require_user)):
    """Kick off the Google OAuth flow."""
    if not (settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET):
        raise HTTPException(503, detail=(
            "Google OAuth is not configured. Set GOOGLE_OAUTH_CLIENT_ID / "
            "GOOGLE_OAUTH_CLIENT_SECRET in your .env."
        ))

    state = secrets.token_urlsafe(24)
    r = await _redis()
    try:
        await r.setex(_state_key(state), 600, str(claims["sub"]))
    finally:
        await r.aclose()

    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": _GMAIL_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "include_granted_scopes": "true",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Complete the Google OAuth flow."""
    if error:
        return RedirectResponse(f"/dashboard?integration_error={error}", status_code=303)
    if not code or not state:
        raise HTTPException(400, detail="Missing code/state")

    r = await _redis()
    try:
        user_id_raw = await r.get(_state_key(state))
        if user_id_raw:
            await r.delete(_state_key(state))
    finally:
        await r.aclose()
    if not user_id_raw:
        raise HTTPException(400, detail="OAuth state expired or invalid")
    user_id = int(user_id_raw)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                    "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                    "redirect_uri": _redirect_uri(),
                    "grant_type": "authorization_code",
                },
            )
            token_resp.raise_for_status()
            tokens = token_resp.json()
            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            expires_in = tokens.get("expires_in")
            scope = tokens.get("scope")

            email = None
            if access_token:
                ui = await client.get(
                    "https://openidconnect.googleapis.com/v1/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if ui.status_code == 200:
                    email = ui.json().get("email")
    except Exception as e:
        logger.error(f"Google OAuth token exchange failed: {e}")
        return RedirectResponse("/dashboard?integration_error=token_exchange", status_code=303)

    if not access_token:
        return RedirectResponse("/dashboard?integration_error=no_access_token", status_code=303)

    await upsert_google(
        session, user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        scope=scope,
        account_email=email,
    )
    await session.commit()
    return RedirectResponse("/dashboard?integration=google", status_code=303)


@router.post("/{provider}/disconnect")
async def disconnect(
    provider: str,
    claims: dict = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    removed = await revoke(session, int(claims["sub"]), provider)
    await session.commit()
    return RedirectResponse(
        f"/dashboard?integration_removed={provider}&n={removed}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
