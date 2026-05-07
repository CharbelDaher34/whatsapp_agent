"""Phone + WhatsApp-OTP authentication and JWT session cookies."""
from datetime import datetime, timedelta
from typing import Optional

import jwt
import redis.asyncio as redis
from fastapi import Cookie, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.db.session import get_session
from app.models.user import User


def _normalize_phone(phone: str) -> str:
    """Strip everything except digits, leaving the bare E.164 numeric form."""
    return "".join(ch for ch in (phone or "") if ch.isdigit())


# ---------------------------------------------------------------------------
# OTP storage (Redis with TTL). We keep a separate failed-attempt counter so
# brute force is rate-limited.
# ---------------------------------------------------------------------------

def _otp_key(phone: str) -> str:
    return f"otp:{phone}"


def _otp_attempts_key(phone: str) -> str:
    return f"otp_attempts:{phone}"


async def _redis() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


async def issue_otp(phone: str) -> str:
    """Generate, store and return a 6-digit OTP for ``phone``."""
    import secrets
    code = f"{secrets.randbelow(1_000_000):06d}"
    r = await _redis()
    try:
        await r.setex(_otp_key(phone), settings.OTP_TTL_SECONDS, code)
        await r.delete(_otp_attempts_key(phone))
    finally:
        await r.aclose()
    logger.info(f"📲 Issued OTP for {phone} (len={len(code)})")
    return code


async def verify_otp(phone: str, code: str) -> bool:
    """Constant-time-ish OTP check. After 5 wrong tries the code is voided."""
    if not code or len(code) != 6 or not code.isdigit():
        return False
    r = await _redis()
    try:
        attempts = await r.incr(_otp_attempts_key(phone))
        if attempts == 1:
            await r.expire(_otp_attempts_key(phone), settings.OTP_TTL_SECONDS)
        if attempts > 5:
            await r.delete(_otp_key(phone))
            return False
        stored = await r.get(_otp_key(phone))
        if not stored:
            return False
        if stored != code:
            return False
        await r.delete(_otp_key(phone))
        await r.delete(_otp_attempts_key(phone))
        return True
    finally:
        await r.aclose()


# ---------------------------------------------------------------------------
# JWT session cookie
# ---------------------------------------------------------------------------

def issue_session_token(user: User) -> str:
    """Mint a signed JWT for ``user``. Use ``set_session_cookie`` on the response."""
    now = datetime.utcnow()
    payload = {
        "sub": str(user.id),
        "phone": user.phone,
        "tier": user.subscription_tier,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.JWT_TTL_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def decode_session_token(token: str) -> dict:
    """Decode + validate the JWT. Raises ``HTTPException(401)`` on failure."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid session")


def set_session_cookie(response, token: str) -> None:
    """Attach the auth cookie to ``response`` (httpOnly, lax, optionally secure)."""
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        max_age=settings.JWT_TTL_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=settings.WEB_BASE_URL.startswith("https://"),
        path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/")


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

async def current_user_optional(
    request: Request,
) -> Optional[dict]:
    """Decode the session cookie if present; return ``None`` otherwise."""
    token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    if not token:
        return None
    try:
        return decode_session_token(token)
    except HTTPException:
        return None


async def require_user(request: Request) -> dict:
    """Require a valid session cookie. 401 otherwise."""
    claims = await current_user_optional(request)
    if not claims:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return claims


async def load_current_user(claims: dict, session: AsyncSession) -> User:
    """Resolve the User row referenced by a set of session claims."""
    user_id = int(claims["sub"])
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    return user
