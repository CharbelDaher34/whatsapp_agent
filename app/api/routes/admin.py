"""Admin API endpoints."""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.plans import PLANS, normalize_tier
from app.db.session import get_session
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.tool import ToolConfig
from app.models.usage import UsageRecord
from app.models.user import User
from app.schemas.admin import (
    ToolResponse,
    UpdateSubscriptionRequest,
    UpdateToolRequest,
    UserResponse,
)
from app.services.queue.user_queue_manager import get_queue_manager
from app.utils.auth import admin_auth

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
    
    tier = normalize_tier(request.tier)
    if tier not in PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tier '{request.tier}'. Must be one of: {sorted(PLANS)}",
        )
    user.subscription_tier = tier
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
    """System statistics and tier distribution."""
    total_users = len(session.exec(select(User)).all())
    active_users = len(session.exec(select(User).where(User.is_active == True)).all())  # noqa: E712
    total_conversations = len(session.exec(select(Conversation)).all())
    total_messages = len(session.exec(select(Message)).all())

    tier_distribution: dict[str, int] = {tier: 0 for tier in PLANS}
    for u in session.exec(select(User)).all():
        tier_distribution[normalize_tier(u.subscription_tier)] = (
            tier_distribution.get(normalize_tier(u.subscription_tier), 0) + 1
        )

    yesterday = datetime.utcnow() - timedelta(hours=24)
    messages_24h = len(session.exec(
        select(Message).where(Message.created_at >= yesterday)
    ).all())
    new_users_24h = len(session.exec(
        select(User).where(User.created_at >= yesterday)
    ).all())

    user_messages = len(session.exec(select(Message).where(Message.sender == "user")).all())
    bot_messages = len(session.exec(
        select(Message).where(Message.sender.in_(["bot", "assistant"]))  # type: ignore[attr-defined]
    ).all())

    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": total_users - active_users,
        "total_conversations": total_conversations,
        "total_messages": total_messages,
        "user_messages": user_messages,
        "bot_messages": bot_messages,
        "tier_distribution": tier_distribution,
        "last_24_hours": {
            "messages": messages_24h,
            "new_users": new_users_24h,
        },
    }


@router.get("/plans")
def list_plans():
    """Return the configured plan tiers and their limits."""
    return {
        name: {
            "name": p.name,
            "display_name": p.display_name,
            "messages_per_day": p.messages_per_day,
            "messages_per_month": p.messages_per_month,
            "history_depth": p.history_depth,
            "model": p.model,
            "tools": sorted(p.tools),
            "inbound_modalities": sorted(p.inbound_modalities),
            "can_generate_images": p.can_generate_images,
            "can_transform_images": p.can_transform_images,
            "can_transcribe_audio": p.can_transcribe_audio,
            "can_read_documents": p.can_read_documents,
        }
        for name, p in PLANS.items()
    }


@router.get("/users/{user_id}/usage")
def get_user_usage(user_id: int, session: Session = Depends(get_session)):
    """Today + month-to-date usage for a single user."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    today = datetime.utcnow().date()
    daily = session.exec(
        select(UsageRecord).where(
            UsageRecord.user_id == user_id,
            UsageRecord.day == today,
        )
    ).first()
    month_records = session.exec(
        select(UsageRecord).where(
            UsageRecord.user_id == user_id,
            UsageRecord.day >= today.replace(day=1),
        )
    ).all()
    monthly_total = sum(r.messages for r in month_records)

    plan = PLANS[normalize_tier(user.subscription_tier)]
    return {
        "user_id": user_id,
        "phone": user.phone,
        "plan": plan.name,
        "daily_used": daily.messages if daily else 0,
        "daily_limit": plan.messages_per_day,
        "monthly_used": monthly_total,
        "monthly_limit": plan.messages_per_month,
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


