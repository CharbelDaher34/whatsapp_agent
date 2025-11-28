"""Health check endpoint with dependency checks."""
from fastapi import APIRouter, status
from typing import Dict, Any
from datetime import datetime
import httpx

from app.core.config import settings
from app.core.logging import logger

router = APIRouter(tags=["health"])


async def check_database() -> Dict[str, Any]:
    """Check database connection."""
    try:
        from app.db.session import engine
        from sqlmodel import text
        
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        return {"status": "healthy", "message": "Database connected"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "message": str(e)}


async def check_redis() -> Dict[str, Any]:
    """Check Redis connection."""
    try:
        from app.queue.connection import check_redis_health
        
        is_healthy = await check_redis_health()
        
        if is_healthy:
            return {"status": "healthy", "message": "Redis connected"}
        else:
            return {"status": "unhealthy", "message": "Redis ping failed"}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {"status": "unhealthy", "message": str(e)}


async def check_whatsapp_api() -> Dict[str, Any]:
    """Check WhatsApp API connectivity."""
    try:
        # Test by checking phone number metadata
        phone_id = settings.WHATSAPP_PHONE_ID.strip().lstrip('=')
        url = f"https://graph.facebook.com/v20.0/{phone_id}"
        
        headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        }
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                return {"status": "healthy", "message": "WhatsApp API accessible"}
            else:
                return {
                    "status": "degraded",
                    "message": f"WhatsApp API returned {response.status_code}"
                }
    except Exception as e:
        logger.error(f"WhatsApp API health check failed: {e}")
        return {"status": "unhealthy", "message": str(e)}


@router.get("/health")
async def health_check():
    """
    Simple health check endpoint.
    Returns 200 OK if service is running.
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": settings.APP_NAME
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check with all dependencies.
    
    Returns:
    - 200: All systems healthy
    - 503: One or more systems unhealthy
    """
    # Check all dependencies
    database_health = await check_database()
    redis_health = await check_redis()
    whatsapp_health = await check_whatsapp_api()
    
    # Determine overall status
    all_healthy = all([
        database_health["status"] == "healthy",
        redis_health["status"] in ["healthy", "degraded"],  # Redis is optional
        whatsapp_health["status"] in ["healthy", "degraded"]
    ])
    
    overall_status = "healthy" if all_healthy else "unhealthy"
    
    response_data = {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "service": settings.APP_NAME,
        "version": "0.1.0",
        "dependencies": {
            "database": database_health,
            "redis": redis_health,
            "whatsapp_api": whatsapp_health
        },
        "configuration": {
            "debug": settings.DEBUG,
            "rate_limit_enabled": settings.RATE_LIMIT_ENABLED,
            "redis_url": settings.REDIS_URL.split("@")[-1] if "@" in settings.REDIS_URL else "localhost"
        }
    }
    
    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return response_data


