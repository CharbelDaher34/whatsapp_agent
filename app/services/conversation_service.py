"""Conversation service for managing user conversations."""
from sqlmodel import Session, select
from typing import List
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User


def get_or_create_active_conversation(session: Session, user: User) -> Conversation:
    """Get or create an active conversation for a user."""
    conversation = session.exec(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .where(Conversation.status == "active")
        .order_by(Conversation.created_at.desc())
    ).first()
    
    if conversation:
        return conversation
    
    conversation = Conversation(user_id=user.id)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def get_conversation_history(session: Session, conversation: Conversation) -> List[str]:
    """Get formatted conversation history (last 2 messages only)."""
    msgs = session.exec(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(2)
    ).all()
    
    # Reverse to get chronological order
    msgs = list(reversed(msgs))
    
    history = []
    for m in msgs:
        prefix = "User:" if m.sender == "user" else "Bot:"
        history.append(f"{prefix} {m.content}")
    return history


