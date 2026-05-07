"""WhatsApp webhook orchestration.

Pipeline:
  1. Parse the raw webhook payload.
  2. Mark the message read.
  3. Resolve user + active conversation.
  4. Enforce plan quota.
  5. Dispatch to the type-specific handler (downloads media if needed).
  6. Persist the inbound message.
  7. Run the AI agent (plan-aware) to generate a reply.
  8. Post-process the reply (image tool output, ask-user no-reply sentinel).
  9. Send to WhatsApp (text/image/none).
 10. Persist bot reply + register usage.
 11. Drain any messages that were queued while we processed this one.
"""
from copy import deepcopy

from app.core.exceptions import RateLimitExceeded, WhatsAppBotError
from app.core.logging import logger
from app.db.session import get_session
from app.services.ai.reply_service import generate_reply_for_user, process_tool_outputs
from app.services.conversation_service import (
    get_conversation_context,
    get_or_create_user_conversation,
    save_bot_message,
    save_user_message,
)
from app.services.whatsapp.interactive import mark_message_read
from app.queue.user_queue_manager import get_queue_manager
from app.services.subscription_service import check_quota, register_message
from app.services.whatsapp.commands import maybe_handle_command, parse_command
from app.services.whatsapp.handlers.registry import handle_message
from app.services.whatsapp.media_handler import upload_media_to_whatsapp
from app.services.whatsapp.parser import MessageType, parse_webhook_payload
from app.services.whatsapp.client import send_whatsapp_image, send_whatsapp_text


async def _process_queued_messages(phone: str, original_payload: dict) -> None:
    """Drain queued messages for `phone` after this request finishes.

    Combines them into one synthetic webhook body and re-enqueues so the AI
    sees them as a single unit. Always releases the per-user lock, even on
    error, so the user can keep messaging.
    """
    queue_manager = get_queue_manager()
    try:
        queued = await queue_manager.get_and_clear_queued_messages(phone)
        await queue_manager.release_user_processing(phone)

        if not queued:
            return

        combined_text = "\n\n".join(queued)
        logger.info(f"📦 Combining {len(queued)} queued messages for {phone}")
        payload = _create_combined_payload(phone, combined_text, original_payload)

        try:
            from app.queue.connection import get_arq_redis
            arq_redis = await get_arq_redis()
            await arq_redis.enqueue_job(
                "process_webhook_message",
                payload,
                _queue_name="whatsapp:webhook",
            )
            logger.info(f"✅ Re-enqueued combined messages for {phone}")
        except Exception as e:
            logger.error(f"Failed to re-enqueue combined messages: {e}")
    except Exception as e:
        logger.error(f"Error draining queued messages: {e}", exc_info=True)
        try:
            await queue_manager.release_user_processing(phone)
        except Exception:
            pass


def _create_combined_payload(phone: str, combined_text: str, template: dict) -> dict:
    """Build a synthetic text webhook from a template and combined body."""
    payload = deepcopy(template)
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [{}])
        if messages:
            msg = messages[0]
            msg.setdefault("text", {})["body"] = combined_text
            msg["type"] = "text"
            msg["from"] = phone
            # Drop fields that no longer apply to the synthetic text message.
            for k in ("image", "video", "audio", "voice", "document", "sticker",
                       "location", "contacts", "interactive", "button", "reaction"):
                msg.pop(k, None)
        return payload
    except Exception as e:
        logger.error(f"Error creating combined payload: {e}")
        return template


def _command_text(message) -> str | None:
    """Return the slash-command text from a message, if applicable.

    Plain text and interactive replies (buttons / list selections whose id
    starts with ``upgrade:``) all map to a command string the command router
    understands.
    """
    if message.message_type == MessageType.TEXT:
        candidate = (message.content.text or "").strip()
        return candidate if parse_command(candidate) else None

    if message.message_type in (MessageType.INTERACTIVE, MessageType.BUTTON):
        rid = (message.content.button_id or message.content.list_id or "").strip()
        if rid.startswith("upgrade:"):
            target = rid.split(":", 1)[1] or ""
            if parse_command(target):
                return f"/{target}"
    return None


async def _send_quota_response(phone: str, quota) -> None:
    """Tell the user politely they've hit their plan limit."""
    try:
        await send_whatsapp_text(phone, quota.upgrade_message())
    except Exception as e:
        logger.error(f"Failed to send quota message to {phone}: {e}")


async def handle_incoming_webhook(payload: dict):
    """Main entry called by the API route (or the queue worker)."""
    message = parse_webhook_payload(payload)
    if not message:
        return {"status": "skipped", "message": "No message"}

    phone = message.from_phone

    if message.message_id:
        try:
            await mark_message_read(message.message_id)
        except Exception as e:
            logger.warning(f"Mark-read failed for {message.message_id}: {e}")

    async with get_session() as session:
        try:
            # 1. Resolve user + conversation.
            user, conversation = await get_or_create_user_conversation(phone, session)

            # 2. Enforce quota up front so we don't burn AI tokens for blocked users.
            quota = await check_quota(user, session)
            if not quota.allowed:
                logger.info(
                    f"🚫 Quota blocked {phone} (reason={quota.reason}, plan={quota.plan.name})"
                )
                await _send_quota_response(phone, quota)
                raise RateLimitExceeded(quota.reason or "quota_exceeded")

            # 3. Slash-command shortcut? Bypasses the AI entirely.
            command_text = _command_text(message)
            if command_text and await maybe_handle_command(
                command_text, user, phone, session,
            ):
                await save_user_message(
                    conversation.id,
                    command_text,
                    message.message_type.value,
                    session,
                )
                await register_message(user, session)
                await session.commit()
                return {"status": "success", "data": {"reply_type": "command"}}

            # 4. Type-specific handler (downloads media, transcribes audio, etc.).
            context = await get_conversation_context(
                conversation, session, limit=quota.plan.history_depth,
            )
            handler_result = await handle_message(message, context)

            # 4. Persist inbound message.
            await save_user_message(
                conversation.id,
                handler_result.processed_content,
                message.message_type.value,
                session,
            )

            if not handler_result.requires_ai:
                # e.g. reactions: don't bother the user with a reply.
                await register_message(user, session)
                await session.commit()
                return {"status": "success", "data": {"reply_type": "none"}}

            # 5. Generate reply.
            ai_reply_text = await generate_reply_for_user(
                user=user,
                conversation=conversation,
                message_content=handler_result.processed_content,
                history=context.history,
                image_data=handler_result.media_data,
                media_type=handler_result.media_type,
                phone=phone,
            )

            # 6. Post-process and send.
            processed = await process_tool_outputs(ai_reply_text)
            tool_calls_used = 0

            if processed.reply_type == "image" and processed.media_path:
                try:
                    media_id = await upload_media_to_whatsapp(processed.media_path)
                    await send_whatsapp_image(
                        phone, media_id=media_id, caption=processed.caption,
                    )
                    tool_calls_used = 1
                except Exception as e:
                    logger.error(f"Image send failed, falling back to text: {e}")
                    fallback = processed.caption or "Sorry, I couldn't send that image."
                    await send_whatsapp_text(phone, fallback)
                    processed = processed.model_copy(update={"reply_type": "text", "content": fallback})
            elif processed.reply_type == "none":
                # Agent already pushed an interactive message — nothing to send here.
                pass
            else:
                if processed.content:
                    await send_whatsapp_text(phone, processed.content)

            # 7. Persist bot reply + register usage.
            if processed.content or processed.reply_type == "image":
                await save_bot_message(
                    conversation.id, processed.content, processed.reply_type, session,
                )
            await register_message(user, session, tool_calls=tool_calls_used)
            await session.commit()

            return {
                "status": "success",
                "data": {"reply_type": processed.reply_type, "plan": quota.plan.name},
            }

        except RateLimitExceeded:
            return {"status": "rate_limited"}
        except WhatsAppBotError as e:
            logger.error(f"WhatsApp bot error: {e}")
            try:
                await send_whatsapp_text(
                    phone, "Sorry, I hit an error processing that. Please try again."
                )
            except Exception:
                pass
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            try:
                await send_whatsapp_text(
                    phone, "Sorry, something went wrong on my end. Please try again."
                )
            except Exception:
                pass
            return {"status": "error", "message": "Internal error"}
        finally:
            await _process_queued_messages(phone, payload)
