"""Redis connection management."""
from typing import Optional
import redis.asyncio as redis
from arq.connections import ArqRedis, create_pool
from app.core.config import settings
from app.core.logging import logger


# Global Redis connection pool
_redis_pool: Optional[redis.Redis] = None
_arq_redis: Optional[ArqRedis] = None


async def get_redis_pool() -> redis.Redis:
    """
    Get or create Redis connection pool.
    
    Returns:
        Redis connection pool for general use
    """
    global _redis_pool
    
    if _redis_pool is None:
        try:
            _redis_pool = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50
            )
            # Test connection
            await _redis_pool.ping()
            logger.info(f"✅ Connected to Redis: {settings.REDIS_URL}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise
    
    return _redis_pool


async def get_arq_redis() -> ArqRedis:
    """
    Get or create ARQ Redis connection for job queue.
    
    Returns:
        ARQ Redis connection for enqueuing jobs
    """
    global _arq_redis
    
    if _arq_redis is None:
        try:
            from arq.connections import RedisSettings
            
            # Parse Redis URL to RedisSettings
            redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
            
            # Create ARQ Redis pool
            _arq_redis = await create_pool(redis_settings)
            logger.info("✅ ARQ Redis pool created")
        except Exception as e:
            logger.error(f"❌ Failed to create ARQ Redis pool: {e}")
            raise
    
    return _arq_redis


async def close_redis_connections():
    """Close all Redis connections."""
    global _redis_pool, _arq_redis
    
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None
        logger.info("Redis connection pool closed")
    
    if _arq_redis:
        await _arq_redis.close()
        _arq_redis = None
        logger.info("ARQ Redis connection closed")


async def check_redis_health() -> bool:
    """
    Check Redis connection health.
    
    Returns:
        True if Redis is healthy, False otherwise
    """
    try:
        pool = await get_redis_pool()
        await pool.ping()
        return True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False

