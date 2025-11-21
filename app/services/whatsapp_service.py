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
from app.services.whatsapp_client import send_whatsapp_text
from app.core.logging import logger


async def handle_incoming_webhook(payload: dict):
    """
    Process incoming WhatsApp webhook.
    Extracts message, saves to DB, generates AI reply, and sends response.
    """
    try:
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages")
        
        if not messages:
            return
        
        msg = messages[0]
        from_phone = msg["from"]
        msg_type = msg["type"]
        
        if msg_type == "text":
            text = msg["text"]["body"]
        else:
            # Future: handle image/document/audio types
            text = f"[{msg_type} message not yet supported]"
        
        # Use a new session for this request
        session_gen = get_session()
        session = next(session_gen)
        
        try:
            user = _get_or_create_user(session, from_phone)
            
            if not can_user_send_message(user):
                await send_whatsapp_text(
                    to=from_phone,
                    message="You've reached your daily limit. Please upgrade your subscription."
                )
                return
            
            conversation = get_or_create_active_conversation(session, user)
            
            # Save user message
            session.add(Message(
                conversation_id=conversation.id,
                sender="user",
                msg_type="text",
                content=text
            ))
            session.commit()
            
            history = get_conversation_history(session, conversation)
            
            reply_text = await generate_reply(user, conversation, text, history)
            
            # Save bot message
            session.add(Message(
                conversation_id=conversation.id,
                sender="bot",
                msg_type="text",
                content=reply_text
            ))
            session.commit()
            
            register_usage(user)
            
            await send_whatsapp_text(to=from_phone, message=reply_text)
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Error in handle_incoming_webhook: {e}")


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


