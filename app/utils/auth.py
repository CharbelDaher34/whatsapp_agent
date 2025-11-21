"""Authentication utilities for admin endpoints."""
from fastapi import Header, HTTPException, status
from app.core.config import settings


def admin_auth(x_admin_key: str = Header(...)):
    """Simple API key authentication for admin endpoints."""
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )
    return True


