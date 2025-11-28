"""Clean, refactored WhatsApp webhook service (~50 lines)."""
from copy import deepcopy
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.services.whatsapp.parser import parse_webhook_payload
from app.services.conversation.flow_service import (
    get_or_create_user_conversation,
    save_user_message,
    save_bot_message,
    get_conversation_context
)
from app.services.subscription_service import can_user_send_message, register_usage
from app.services.whatsapp.handlers.registry import handle_message
from app.services.ai.reply_service import generate_reply_for_user, process_tool_outputs
from app.services.whatsapp.response_builder import (
    build_text_response,
    build_image_response,
    build_rate_limit_response
)
from app.services.whatsapp.media_handler import upload_media_to_whatsapp
from app.services.whatsapp_client import send_whatsapp_text, send_whatsapp_image
from app.services.interactive_messages import mark_message_read
from app.services.queue.user_queue_manager import get_queue_manager
from app.core.logging import logger
from app.core.exceptions import RateLimitExceeded, WhatsAppBotError


async def _process_queued_messages(phone: str, original_payload: dict):
    """
    Process queued messages after current message completes.
    Combines all queued messages and re-enqueues as single request.
    
    Args:
        phone: User's phone number
        original_payload: Original webhook payload to use as template
    """
    queue_manager = get_queue_manager()
    
    try:
        # Get all queued messages and clear queue
        queued_messages = await queue_manager.get_and_clear_queued_messages(phone)
        
        # Release processing lock
        await queue_manager.release_user_processing(phone)
        
        if queued_messages:
            # Combine all messages with separator
            combined_text = "\n\n".join(queued_messages)
            logger.info(f"📦 Combining {len(queued_messages)} queued messages for {phone}")
            logger.debug(f"Combined text: '{combined_text[:200]}...'")
            
            # Create new payload with combined messages
            combined_payload = _create_combined_payload(phone, combined_text, original_payload)
            
            # Re-enqueue combined message
            try:
                from app.queue.connection import get_arq_redis
                arq_redis = await get_arq_redis()
                await arq_redis.enqueue_job(
                    'process_webhook_message',
                    combined_payload,
                    _queue_name='whatsapp:webhook'
                )
                logger.info(f"✅ Re-enqueued combined messages for {phone}")
            except Exception as e:
                logger.error(f"Failed to re-enqueue combined messages: {e}")
        else:
            logger.debug(f"No queued messages for {phone}")
            
    except Exception as e:
        logger.error(f"Error processing queued messages: {e}", exc_info=True)
        # Always release lock on error
        try:
            await queue_manager.release_user_processing(phone)
        except:
            pass


def _create_combined_payload(phone: str, combined_text: str, template: dict) -> dict:
    """
    Create a webhook payload with combined message text.
    
    Args:
        phone: User's phone number
        combined_text: Combined message text
        template: Original payload to use as template
        
    Returns:
        New payload dict with combined message
    """
    # Create a deep copy of the template
    payload = deepcopy(template)
    
    try:
        # Navigate to message content and update it
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [{}])
        
        if messages:
            msg = messages[0]
            # Update message text
            if "text" not in msg:
                msg["text"] = {}
            msg["text"]["body"] = combined_text
            msg["type"] = "text"
            
            # Update phone
            msg["from"] = phone
            
        return payload
    except Exception as e:
        logger.error(f"Error creating combined payload: {e}")
        return template


async def handle_incoming_webhook(payload: dict):
    """
    Clean webhook handler using focused services with message batching support.
    """
    # 1. Parse webhook
    message = parse_webhook_payload(payload)
    if not message:
        return {"status": "skipped", "message": "No message"}
    
    phone = message.from_phone
    
    # Mark as read immediately
    if message.message_id:
        await mark_message_read(message.message_id)
    
    async with get_session() as session:
        try:
            # 2. Get/create user and conversation
            user, conversation = await get_or_create_user_conversation(
                message.from_phone, session
            )
            
            # 3. Check rate limits
            if not can_user_send_message(user):
                response = build_rate_limit_response(message.from_phone)
                await send_whatsapp_text(response.to, response.text)
                raise RateLimitExceeded("User exceeded rate limit")
            
            # 4. Handle message by type (downloads media if needed)
            handler_result = await handle_message(
                message,
                await get_conversation_context(conversation, session)
            )
            
            # 5. Save incoming message
            await save_user_message(
                conversation.id,
                handler_result.processed_content,
                message.message_type.value,
                session
            )
            
            # 6. Generate AI reply
            ai_reply_text = await generate_reply_for_user(
                user,
                conversation,
                handler_result.processed_content,
                (await get_conversation_context(conversation, session)).history,
                image_data=handler_result.media_data,
                media_type=handler_result.media_type,
                phone=phone  # Pass phone for tool context
            )
            
            # 7. Process tool outputs (check for generated images, etc.)
            processed_reply = await process_tool_outputs(ai_reply_text)
            
            # 8. Send response to WhatsApp
            if processed_reply.reply_type == "image" and processed_reply.media_path:
                media_id = await upload_media_to_whatsapp(processed_reply.media_path)
                await send_whatsapp_image(
                    message.from_phone,
                    media_id=media_id,
                    caption=processed_reply.caption
                )
            else:
                await send_whatsapp_text(message.from_phone, processed_reply.content)
            
            # 9. Save bot message
            await save_bot_message(
                conversation.id,
                processed_reply.content,
                processed_reply.reply_type,
                session
            )
            
            # 10. Register usage
            register_usage(user)
            await session.commit()
            
            return {
                "status": "success",
                "message": "Webhook processed",
                "data": {"reply_type": processed_reply.reply_type}
            }
            
        except RateLimitExceeded:
            return {"status": "rate_limited", "message": "Rate limit exceeded"}
        except WhatsAppBotError as e:
            logger.error(f"WhatsApp bot error: {e}")
            # Send error message to user
            await send_whatsapp_text(
                message.from_phone,
                "Sorry, I encountered an error. Please try again."
            )
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return {"status": "error", "message": "Internal error"}
        finally:
            # Process queued messages - this runs even if there was an error
            await _process_queued_messages(phone, payload)

