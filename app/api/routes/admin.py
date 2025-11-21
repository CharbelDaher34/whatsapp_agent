"""Admin API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
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
    """Get system statistics."""
    total_users = len(session.exec(select(User)).all())
    active_users = len(session.exec(select(User).where(User.is_active == True)).all())
    total_conversations = len(session.exec(select(Conversation)).all())
    total_messages = len(session.exec(select(Message)).all())
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_conversations": total_conversations,
        "total_messages": total_messages
    }


