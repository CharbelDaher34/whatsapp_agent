"""Message queue middleware for per-user request handling."""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import json
from app.services.queue.user_queue_manager import get_queue_manager
from app.core.logging import logger


class MessageQueueMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle per-user message queuing.
    
    If a user has a message being processed, queue subsequent messages
    and return immediately. When first message completes, all queued
    messages are combined and processed together.
    """
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Intercept webhook POST requests and manage queuing."""
        
        # Only intercept webhook POST requests
        if request.url.path != "/webhook" or request.method != "POST":
            return await call_next(request)
        
        try:
            queue_manager = get_queue_manager()
            
            # Read body once and cache it
            body = await request.body()
            
            # Parse payload to extract phone and message
            try:
                payload = json.loads(body)
                phone, message_text = self._extract_phone_and_message(payload)
                
                if not phone or not message_text:
                    # Can't extract, pass through
                    return await self._continue_request(request, call_next, body)
                
            except Exception as e:
                logger.error(f"Error parsing payload for queue check: {e}")
                return await self._continue_request(request, call_next, body)
            
            # Check if user is currently being processed
            is_processing = await queue_manager.is_user_processing(phone)
            
            if is_processing:
                # User is busy, queue this message
                queue_size = await queue_manager.append_message(phone, message_text)
                
                if queue_size == -1:
                    # Queue is full
                    logger.warning(f"⚠️  Queue full for {phone}, rejecting message")
                    return JSONResponse(
                        {"status": "error", "message": "Queue full"},
                        status_code=429
                    )
                
                logger.info(f"📥 Queued message for {phone} (queue: {queue_size}): '{message_text[:50]}...'")
                return JSONResponse({"status": "queued", "queue_position": queue_size})
            
            # User is free, mark as processing and continue
            locked = await queue_manager.mark_user_processing(phone)
            
            if not locked:
                # Race condition: another request just started processing
                # Queue this one
                queue_size = await queue_manager.append_message(phone, message_text)
                logger.info(f"📥 Queued (race condition) for {phone}: '{message_text[:50]}...'")
                return JSONResponse({"status": "queued", "queue_position": queue_size})
            
            logger.debug(f"🔓 User {phone} free, processing message")
            
            # Continue with normal processing
            return await self._continue_request(request, call_next, body)
            
        except Exception as e:
            logger.error(f"Error in message queue middleware: {e}", exc_info=True)
            # On error, pass through to avoid blocking
            return await call_next(request)
    
    def _extract_phone_and_message(self, payload: dict) -> tuple[str, str]:
        """
        Extract phone number and message text from webhook payload.
        
        Returns:
            Tuple of (phone, message_text) or (None, None)
        """
        try:
            entry = payload.get("entry", [])[0]
            changes = entry.get("changes", [])[0]
            value = changes.get("value", {})
            messages = value.get("messages")
            
            if not messages:
                return None, None
            
            msg = messages[0]
            phone = msg.get("from")
            msg_type = msg.get("type")
            
            # Extract message text based on type
            if msg_type == "text":
                message_text = msg.get("text", {}).get("body", "")
            elif msg_type == "image":
                message_text = msg.get("image", {}).get("caption", "[Image]")
            elif msg_type == "video":
                message_text = msg.get("video", {}).get("caption", "[Video]")
            elif msg_type == "audio":
                message_text = "[Audio]"
            elif msg_type == "interactive":
                interactive = msg.get("interactive", {})
                if interactive.get("type") == "button_reply":
                    message_text = interactive.get("button_reply", {}).get("title", "[Button]")
                elif interactive.get("type") == "list_reply":
                    message_text = interactive.get("list_reply", {}).get("title", "[List]")
                else:
                    message_text = f"[Interactive: {interactive.get('type')}]"
            else:
                message_text = f"[{msg_type}]"
            
            return phone, message_text
            
        except Exception as e:
            logger.error(f"Error extracting phone/message: {e}")
            return None, None
    
    async def _continue_request(self, request: Request, call_next: Callable, body: bytes):
        """Continue with request, restoring body."""
        # Create a new request with the cached body
        async def receive():
            return {"type": "http.request", "body": body}
        
        request._receive = receive
        return await call_next(request)

