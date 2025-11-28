"""Clean, refactored WhatsApp webhook service (~50 lines)."""
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
from app.core.logging import logger
from app.core.exceptions import RateLimitExceeded, WhatsAppBotError


async def handle_incoming_webhook(payload: dict):
    """
    Clean webhook handler using focused services (~50 lines).
    """
    # 1. Parse webhook
    message = parse_webhook_payload(payload)
    if not message:
        return {"status": "skipped", "message": "No message"}
    
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
                image_data=handler_result.media_data
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

