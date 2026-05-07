"""User-specific message queue manager using Redis."""
from typing import List, Optional
import redis.asyncio as redis
from app.core.config import settings
from app.core.logging import logger


class UserQueueManager:
    """Manage per-user message queues in Redis."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.enabled = settings.USER_QUEUE_ENABLED
        self.ttl = settings.USER_QUEUE_TTL
        self.max_size = settings.USER_QUEUE_MAX_SIZE
    
    async def _get_redis(self) -> redis.Redis:
        """Get Redis client, create if needed."""
        if self.redis_client is None:
            try:
                self.redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True
                )
                await self.redis_client.ping()
            except Exception as e:
                logger.error(f"Failed to connect to Redis for queue: {e}")
                raise
        return self.redis_client
    
    def _lock_key(self, phone: str) -> str:
        """Get Redis key for processing lock."""
        return f"user_processing:{phone}"
    
    def _queue_key(self, phone: str) -> str:
        """Get Redis key for message queue."""
        return f"user_queue:{phone}"
    
    async def is_user_processing(self, phone: str) -> bool:
        """Check if user has an active processing lock."""
        if not self.enabled:
            return False
        
        try:
            redis_client = await self._get_redis()
            exists = await redis_client.exists(self._lock_key(phone))
            return bool(exists)
        except Exception as e:
            logger.error(f"Error checking user processing status: {e}")
            return False  # Fail open
    
    async def mark_user_processing(self, phone: str, ttl: Optional[int] = None) -> bool:
        """
        Mark user as currently processing a message.
        
        Args:
            phone: User's phone number
            ttl: Time to live in seconds (default from config)
            
        Returns:
            True if lock acquired, False if already locked
        """
        if not self.enabled:
            return True
        
        try:
            redis_client = await self._get_redis()
            ttl = ttl or self.ttl
            
            # Use SET with NX (only set if not exists) and EX (expiry)
            result = await redis_client.set(
                self._lock_key(phone),
                "1",
                nx=True,  # Only set if key doesn't exist
                ex=ttl   # Expire after TTL seconds
            )
            
            if result:
                logger.debug(f"🔒 Locked user {phone} for processing (TTL: {ttl}s)")
                return True
            else:
                logger.debug(f"⏳ User {phone} already locked")
                return False
                
        except Exception as e:
            logger.error(f"Error marking user processing: {e}")
            return True  # Fail open - allow processing
    
    async def release_user_processing(self, phone: str) -> None:
        """Release processing lock for user."""
        if not self.enabled:
            return
        
        try:
            redis_client = await self._get_redis()
            await redis_client.delete(self._lock_key(phone))
            logger.debug(f"🔓 Released lock for user {phone}")
        except Exception as e:
            logger.error(f"Error releasing user lock: {e}")
    
    async def append_message(self, phone: str, message_text: str) -> int:
        """
        Append a message to user's queue.
        
        Args:
            phone: User's phone number
            message_text: Message content to queue
            
        Returns:
            Queue size after append, or -1 if queue is full
        """
        if not self.enabled:
            return 0
        
        try:
            redis_client = await self._get_redis()
            queue_key = self._queue_key(phone)
            
            # Check queue size
            current_size = await redis_client.llen(queue_key)
            if current_size >= self.max_size:
                logger.warning(f"⚠️  Queue full for {phone} (max: {self.max_size})")
                return -1
            
            # Append to queue
            new_size = await redis_client.rpush(queue_key, message_text)
            
            # Set expiry to prevent stale queues
            await redis_client.expire(queue_key, self.ttl)
            
            logger.info(f"📥 Queued message for {phone} (queue size: {new_size})")
            return new_size
            
        except Exception as e:
            logger.error(f"Error appending message to queue: {e}")
            return 0
    
    async def get_and_clear_queued_messages(self, phone: str) -> List[str]:
        """
        Get all queued messages and clear the queue atomically.
        
        Args:
            phone: User's phone number
            
        Returns:
            List of queued message texts
        """
        if not self.enabled:
            return []
        
        try:
            redis_client = await self._get_redis()
            queue_key = self._queue_key(phone)
            
            # Get all messages atomically with LRANGE then DELETE
            # Use pipeline for atomicity
            pipe = redis_client.pipeline()
            pipe.lrange(queue_key, 0, -1)  # Get all
            pipe.delete(queue_key)  # Clear queue
            results = await pipe.execute()
            
            messages = results[0]  # First command result
            
            if messages:
                logger.info(f"📦 Retrieved {len(messages)} queued messages for {phone}")
            
            return messages
            
        except Exception as e:
            logger.error(f"Error getting queued messages: {e}")
            return []
    
    async def get_queue_size(self, phone: str) -> int:
        """Get current queue size for user."""
        if not self.enabled:
            return 0
        
        try:
            redis_client = await self._get_redis()
            size = await redis_client.llen(self._queue_key(phone))
            return size
        except Exception as e:
            logger.error(f"Error getting queue size: {e}")
            return 0
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()


# Global instance
_queue_manager: Optional[UserQueueManager] = None


def get_queue_manager() -> UserQueueManager:
    """Get global queue manager instance."""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = UserQueueManager()
    return _queue_manager

