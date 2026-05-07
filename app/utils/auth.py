"""Authentication utilities for admin endpoints."""
from typing import Optional

from fastapi import Header, HTTPException, status

from app.core.config import settings


def admin_auth(x_admin_key: Optional[str] = Header(default=None)):
    """API-key auth for /admin endpoints.

    Returns 401 (not 422) when the header is missing or wrong, so clients see
    a consistent auth failure regardless of whether they forgot or provided
    the wrong key.
    """
    if not x_admin_key or x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "X-Admin-Key"},
        )
    return True
