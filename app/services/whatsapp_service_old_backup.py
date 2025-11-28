"""WhatsApp service for handling incoming messages."""
from sqlmodel import Session, select
from app.db.session import get_session
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.subscription_service import can_user_send_message, register_usage
from app.services.conversation_service import (
    get_or_create_active_conversation,
    get_conversation_history
)
from app.services.ai_router import generate_reply
from app.services.whatsapp_client import (
    send_whatsapp_text,
    get_media_url,
    download_media,
    send_whatsapp_image,
    upload_media,
    send_typing_indicator
)
from app.services.interactive_messages import mark_message_read
from app.core.logging import logger


async def handle_incoming_webhook(payload: dict):
    """
    Process incoming WhatsApp webhook.
    Extracts message, saves to DB, generates AI reply, and sends response.
    Returns a response dictionary with status and data.
    Sends only ONE message to WhatsApp per webhook.
    """
    response = {
        "status": "success",
        "message": "Webhook processed",
        "data": {}
    }
    
    # WhatsApp response payload - will be sent once at the end
    whatsapp_payload = None
    to_phone = None
    
    try:
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages")
        
        if not messages:
            # Log what kind of event this is (likely status update)
            if value.get("statuses"):
                logger.info("Received status update (ack/delivered/read)")
            else:
                logger.info(f"Received non-message event. Value keys: {list(value.keys())}")
                
            response["status"] = "skipped"
            response["message"] = "No messages in payload"
            return response
        
        msg = messages[0]
        from_phone = msg["from"]
        to_phone = from_phone
        msg_type = msg["type"]
        msg_id = msg.get("id")
        
        # Mark message as read immediately
        if msg_id:
            await mark_message_read(msg_id)
        
        # Extract message content and media
        image_data = None
        video_url = None
        text = ""
        
        if msg_type == "text":
            text = msg["text"]["body"]
        elif msg_type == "interactive":
            # Handle button or list reply
            interactive = msg.get("interactive", {})
            interactive_type = interactive.get("type")
            
            if interactive_type == "button_reply":
                # User clicked a button
                button_reply = interactive.get("button_reply", {})
                button_id = button_reply.get("id")
                button_title = button_reply.get("title")
                text = f"[Button: {button_title}] (id: {button_id})"
                logger.info(f"User clicked button: {button_title} ({button_id})")
            
            elif interactive_type == "list_reply":
                # User selected from a list
                list_reply = interactive.get("list_reply", {})
                list_id = list_reply.get("id")
                list_title = list_reply.get("title")
                text = f"[List Selection: {list_title}] (id: {list_id})"
                logger.info(f"User selected from list: {list_title} ({list_id})")
            
            else:
                text = f"[Interactive {interactive_type} message]"
        elif msg_type == "image":
            # Handle image message - download binary content
            image_id = msg["image"]["id"]
            caption = msg["image"].get("caption", "")
            text = caption if caption else "[User sent an image]"
            
            # Download image binary content
            try:
                media_url = await get_media_url(image_id)
                image_data = await download_media(media_url)
            except Exception as e:
                logger.error(f"Failed to download image: {e}")
                text += " (Failed to download image)"
        elif msg_type == "video":
            # Handle video message
            video_id = msg["video"]["id"]
            caption = msg["video"].get("caption", "")
            text = caption if caption else "[User sent a video]"
            
            # Get video URL
            try:
                video_url = await get_media_url(video_id)
            except Exception as e:
                logger.error(f"Failed to get video URL: {e}")
                text += " (Failed to download video)"
        elif msg_type in ["audio", "document", "voice"]:
            # Handle other media types
            media_id = msg.get(msg_type, {}).get("id", "")
            text = f"[User sent {msg_type}]"
            # For now, we just acknowledge these types
            # In the future, we could download and process them
        else:
            text = f"[{msg_type} message not yet supported]"
        
        # Use a new session for this request
        session_gen = get_session()
        session = next(session_gen)
        
        try:
            user = _get_or_create_user(session, from_phone)
            
            if not can_user_send_message(user):
                # Build rate limit message payload
                whatsapp_payload = {
                    "type": "text",
                    "message": "You've reached your daily limit. Please upgrade your subscription."
                }
                response["status"] = "limited"
                response["message"] = "User reached daily limit"
                response["data"] = {"phone": from_phone, "user_id": user.id}
            else:
                conversation = get_or_create_active_conversation(session, user)
                
                # Save user message
                session.add(Message(
                    conversation_id=conversation.id,
                    sender="user",
                    msg_type=msg_type,
                    content=text
                ))
                session.commit()
                
                history = get_conversation_history(session, conversation)
                
                # Send typing indicator (shows "typing..." in chat)
                await send_typing_indicator(from_phone, is_typing=True)
                
                # Generate reply (pass image_data if present)
                reply_text = await generate_reply(user, conversation, text, history, image_data=image_data)
                
                # Clear typing indicator
                await send_typing_indicator(from_phone, is_typing=False)
                
                # Check for generated image URL in reply
                if "IMAGE_URL:" in reply_text:
                    # Extract URL and clean text
                    import os
                    import re
                    
                    parts = reply_text.split("IMAGE_URL:")
                    caption_text = parts[0].strip()
                    
                    # Extract path and clean it (remove markdown syntax, trailing punctuation)
                    raw_path = parts[1].strip().split()[0] if parts[1].strip() else ""
                    # Remove trailing punctuation like ), ], etc.
                    gen_image_path = re.sub(r'[)\]}>"\'\s]+$', '', raw_path)
                    
                    logger.info(f"🖼️  Extracted image path: '{gen_image_path}'")
                    
                    # Validate the path is real (not a hallucinated placeholder)
                    is_valid_path = False
                    if gen_image_path.startswith("http"):
                        is_valid_path = True
                    elif gen_image_path:
                        # Check if file exists (handle both absolute and relative paths)
                        if os.path.exists(gen_image_path) and os.path.isfile(gen_image_path):
                            is_valid_path = True
                        else:
                            logger.warning(f"File not found at: {gen_image_path}")
                            logger.warning(f"Current working directory: {os.getcwd()}")
                            logger.warning(f"Absolute path would be: {os.path.abspath(gen_image_path)}")
                    
                    if not is_valid_path:
                        logger.warning(f"Invalid image path detected: '{gen_image_path}'")
                        # Fall back to text response
                        whatsapp_payload = {
                            "type": "text",
                            "message": reply_text.replace("IMAGE_URL:" + gen_image_path, "").strip() or "I tried to generate an image but encountered an issue. Please try again."
                        }
                        response["data"] = {
                            "reply_type": "text",
                            "content": whatsapp_payload["message"]
                        }
                    elif not gen_image_path.startswith("http"):
                        # It's a local file, upload it first
                        try:
                            media_id = await upload_media(gen_image_path)
                            whatsapp_payload = {
                                "type": "image",
                                "media_id": media_id,
                                "caption": caption_text if caption_text else None
                            }
                            response["data"] = {
                                "reply_type": "image",
                                "media_id": media_id,
                                "caption": caption_text
                            }
                        except Exception as e:
                            logger.error(f"Failed to upload/send local image: {e}")
                            whatsapp_payload = {
                                "type": "text",
                                "message": "[Error sending generated image]"
                            }
                            response["status"] = "error"
                            response["message"] = "Failed to send generated image"
                            response["data"] = {"error": str(e)}
                    else:
                        # URL-based image (http/https)
                        whatsapp_payload = {
                            "type": "image",
                            "image_url": gen_image_path,
                            "caption": caption_text if caption_text else None
                        }
                        response["data"] = {
                            "reply_type": "image",
                            "image_url": gen_image_path,
                            "caption": caption_text
                        }
                    
                    # Save bot message (image)
                    session.add(Message(
                        conversation_id=conversation.id,
                        sender="bot",
                        msg_type="image",
                        content=f"Generated image: {gen_image_path}"
                    ))
                else:
                    # Normal text reply
                    whatsapp_payload = {
                        "type": "text",
                        "message": reply_text
                    }
                    response["data"] = {
                        "reply_type": "text",
                        "content": reply_text
                    }
                    
                    # Save bot message
                    session.add(Message(
                        conversation_id=conversation.id,
                        sender="bot",
                        msg_type="text",
                        content=reply_text
                    ))
                
                session.commit()
                register_usage(user)
            
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Error in handle_incoming_webhook: {e}")
        response["status"] = "error"
        response["message"] = str(e)
        response["data"] = {}
        whatsapp_payload = {
            "type": "text",
            "message": "Sorry, I encountered an error processing your message."
        }
    
    # Send the response to WhatsApp - SINGLE SEND at the end
    if whatsapp_payload and to_phone:
        await _send_whatsapp_response(to_phone, whatsapp_payload)
    
    return response


async def _send_whatsapp_response(to: str, payload: dict):
    """
    Send a single response to WhatsApp based on the payload type.
    This ensures only ONE message is sent per webhook processing.
    """
    try:
        if payload["type"] == "text":
            await send_whatsapp_text(to=to, message=payload["message"])
        elif payload["type"] == "image":
            if "media_id" in payload:
                await send_whatsapp_image(
                    to=to,
                    image_url=None,
                    media_id=payload["media_id"],
                    caption=payload.get("caption")
                )
            else:
                await send_whatsapp_image(
                    to=to,
                    image_url=payload["image_url"],
                    caption=payload.get("caption")
                )
    except Exception as e:
        logger.error(f"Failed to send WhatsApp response: {e}")


def _get_or_create_user(session: Session, phone: str) -> User:
    """Get or create a user by phone number."""
    user = session.exec(
        select(User).where(User.phone == phone)
    ).first()
    
    if user:
        return user
    
    user = User(phone=phone)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


