"""Admin API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from app.db.session import get_session
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.tool import ToolConfig
from app.utils.auth import admin_auth
from app.schemas.admin import (
    UserResponse,
    UpdateSubscriptionRequest,
    UpdateToolRequest,
    ToolResponse
)
from app.services.queue.user_queue_manager import get_queue_manager
from datetime import datetime

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(admin_auth)]
)


@router.get("/users", response_model=List[UserResponse])
def list_users(session: Session = Depends(get_session)):
    """List all users."""
    users = session.exec(select(User)).all()
    return users


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, session: Session = Depends(get_session)):
    """Get user by ID."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}/subscription", response_model=UserResponse)
def update_user_subscription(
    user_id: int,
    request: UpdateSubscriptionRequest,
    session: Session = Depends(get_session)
):
    """Update user subscription tier."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.subscription_tier = request.tier
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.patch("/users/{user_id}/status")
def toggle_user_status(user_id: int, is_active: bool, session: Session = Depends(get_session)):
    """Activate or deactivate a user."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = is_active
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.get("/users/{user_id}/conversations")
def get_user_conversations(user_id: int, session: Session = Depends(get_session)):
    """Get all conversations for a user."""
    conversations = session.exec(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
    ).all()
    return conversations


@router.get("/users/{user_id}/messages")
def get_user_messages(user_id: int, limit: int = 50, session: Session = Depends(get_session)):
    """Get recent messages for a user."""
    conversations = session.exec(
        select(Conversation).where(Conversation.user_id == user_id)
    ).all()
    
    conversation_ids = [c.id for c in conversations]
    
    messages = session.exec(
        select(Message)
        .where(Message.conversation_id.in_(conversation_ids))
        .order_by(Message.created_at.desc())
        .limit(limit)
    ).all()
    
    return messages


@router.get("/tools", response_model=List[ToolResponse])
def list_tools(session: Session = Depends(get_session)):
    """List all tool configurations."""
    tools = session.exec(select(ToolConfig)).all()
    return tools


@router.get("/tools/{name}", response_model=ToolResponse)
def get_tool(name: str, session: Session = Depends(get_session)):
    """Get tool configuration by name."""
    tool = session.exec(
        select(ToolConfig).where(ToolConfig.name == name)
    ).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.patch("/tools/{name}", response_model=ToolResponse)
def update_tool(
    name: str,
    request: UpdateToolRequest,
    session: Session = Depends(get_session)
):
    """Update tool configuration."""
    tool = session.exec(
        select(ToolConfig).where(ToolConfig.name == name)
    ).first()
    
    if not tool:
        tool = ToolConfig(
            name=name,
            enabled=request.enabled,
            min_tier=request.min_tier
        )
    else:
        tool.enabled = request.enabled
        tool.min_tier = request.min_tier
        tool.updated_at = datetime.utcnow()
    
    session.add(tool)
    session.commit()
    session.refresh(tool)
    return tool


@router.get("/stats")
def get_stats(session: Session = Depends(get_session)):
    """Get system statistics and analytics."""
    from datetime import datetime, timedelta
    
    total_users = len(session.exec(select(User)).all())
    active_users = len(session.exec(select(User).where(User.is_active == True)).all())
    total_conversations = len(session.exec(select(Conversation)).all())
    total_messages = len(session.exec(select(Message)).all())
    
    # User tier distribution
    free_users = len(session.exec(select(User).where(User.subscription_tier == "free")).all())
    plus_users = len(session.exec(select(User).where(User.subscription_tier == "plus")).all())
    pro_users = len(session.exec(select(User).where(User.subscription_tier == "pro")).all())
    
    # Recent activity (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(hours=24)
    messages_24h = len(session.exec(
        select(Message).where(Message.created_at >= yesterday)
    ).all())
    
    new_users_24h = len(session.exec(
        select(User).where(User.created_at >= yesterday)
    ).all())
    
    # Messages by sender
    user_messages = len(session.exec(select(Message).where(Message.sender == "user")).all())
    bot_messages = len(session.exec(select(Message).where(Message.sender == "bot")).all())
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": total_users - active_users,
        "total_conversations": total_conversations,
        "total_messages": total_messages,
        "user_messages": user_messages,
        "bot_messages": bot_messages,
        "tier_distribution": {
            "free": free_users,
            "plus": plus_users,
            "pro": pro_users
        },
        "last_24_hours": {
            "messages": messages_24h,
            "new_users": new_users_24h
        }
    }


@router.patch("/conversations/{conversation_id}/close")
def close_conversation(
    conversation_id: int,
    session: Session = Depends(get_session)
):
    """Close/archive a conversation."""
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conversation.status = "closed"
    conversation.updated_at = datetime.utcnow()
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    
    return conversation


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    session: Session = Depends(get_session)
):
    """Delete a conversation and all its messages."""
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Delete all messages in this conversation
    messages = session.exec(
        select(Message).where(Message.conversation_id == conversation_id)
    ).all()
    
    for msg in messages:
        session.delete(msg)
    
    # Delete conversation
    session.delete(conversation)
    session.commit()
    
    return {"status": "deleted", "conversation_id": conversation_id}


@router.get("/conversations")
def list_all_conversations(
    status: Optional[str] = None,
    limit: int = 100,
    session: Session = Depends(get_session)
):
    """List all conversations with optional filtering."""
    query = select(Conversation).order_by(Conversation.updated_at.desc())
    
    if status:
        query = query.where(Conversation.status == status)
    
    conversations = session.exec(query.limit(limit)).all()
    
    return conversations


@router.get("/queue/status/{phone}")
async def get_queue_status(phone: str):
    """
    Check queue status for a specific user.
    
    Args:
        phone: User's phone number
        
    Returns:
        Queue status information
    """
    queue_manager = get_queue_manager()
    
    return {
        "phone": phone,
        "is_processing": await queue_manager.is_user_processing(phone),
        "queue_size": await queue_manager.get_queue_size(phone),
        "max_queue_size": queue_manager.max_size,
        "queue_enabled": queue_manager.enabled
    }


