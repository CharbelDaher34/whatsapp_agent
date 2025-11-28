"""Broadcast messaging endpoints for admins."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_session
from app.models.user import User
from app.models.broadcast import Broadcast
from app.utils.auth import admin_auth
from app.services.whatsapp_client import send_whatsapp_text, send_whatsapp_image
from app.core.logging import logger


router = APIRouter(
    prefix="/admin/broadcast",
    tags=["admin", "broadcast"],
    dependencies=[Depends(admin_auth)]
)


class BroadcastRequest(BaseModel):
    """Request to create a broadcast."""
    message: str
    target_tier: Optional[str] = None  # None = all, "free", "plus", "pro"
    target_status: str = "active"  # "active", "all"
    media_url: Optional[str] = None
    media_type: Optional[str] = None  # "image", etc.
    scheduled_at: Optional[datetime] = None


class BroadcastResponse(BaseModel):
    """Broadcast response."""
    id: int
    message: str
    target_tier: Optional[str]
    status: str
    total_recipients: int
    sent_count: int
    failed_count: int
    created_at: datetime


async def send_broadcast_messages(broadcast_id: int, session: Session):
    """
    Background task to send broadcast messages.
    
    Args:
        broadcast_id: Broadcast ID to process
        session: Database session
    """
    try:
        broadcast = session.get(Broadcast, broadcast_id)
        if not broadcast:
            logger.error(f"Broadcast {broadcast_id} not found")
            return
        
        # Update status
        broadcast.status = "in_progress"
        broadcast.started_at = datetime.utcnow()
        session.add(broadcast)
        session.commit()
        
        # Get target users
        query = select(User)
        
        if broadcast.target_status == "active":
            query = query.where(User.is_active == True)
        
        if broadcast.target_tier:
            query = query.where(User.subscription_tier == broadcast.target_tier)
        
        users = session.exec(query).all()
        broadcast.total_recipients = len(users)
        session.add(broadcast)
        session.commit()
        
        logger.info(f"📢 Broadcasting to {len(users)} users...")
        
        # Send messages
        sent = 0
        failed = 0
        
        for user in users:
            try:
                if broadcast.media_url and broadcast.media_type == "image":
                    await send_whatsapp_image(
                        to=user.phone,
                        image_url=broadcast.media_url,
                        caption=broadcast.message
                    )
                else:
                    await send_whatsapp_text(
                        to=user.phone,
                        message=broadcast.message
                    )
                sent += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to {user.phone}: {e}")
                failed += 1
        
        # Update broadcast stats
        broadcast.sent_count = sent
        broadcast.failed_count = failed
        broadcast.status = "completed"
        broadcast.completed_at = datetime.utcnow()
        session.add(broadcast)
        session.commit()
        
        logger.info(f"✅ Broadcast completed: {sent} sent, {failed} failed")
        
    except Exception as e:
        logger.error(f"Error sending broadcast: {e}", exc_info=True)
        if broadcast:
            broadcast.status = "failed"
            session.add(broadcast)
            session.commit()


@router.post("", response_model=BroadcastResponse)
async def create_broadcast(
    request: BroadcastRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """
    Create and send a broadcast message.
    
    The broadcast will be sent asynchronously in the background.
    """
    # Validate tier
    if request.target_tier and request.target_tier not in ["free", "plus", "pro"]:
        raise HTTPException(status_code=400, detail="Invalid tier")
    
    # Create broadcast record
    broadcast = Broadcast(
        message=request.message,
        target_tier=request.target_tier,
        target_status=request.target_status,
        media_url=request.media_url,
        media_type=request.media_type,
        scheduled_at=request.scheduled_at,
        status="pending"
    )
    
    session.add(broadcast)
    session.commit()
    session.refresh(broadcast)
    
    # Schedule broadcast (immediate or scheduled)
    if request.scheduled_at and request.scheduled_at > datetime.utcnow():
        logger.info(f"Broadcast {broadcast.id} scheduled for {request.scheduled_at}")
        # TODO: Implement scheduling with APScheduler or Celery
        # For now, just queue it immediately
    
    # Send in background
    background_tasks.add_task(send_broadcast_messages, broadcast.id, session)
    
    logger.info(f"📢 Broadcast {broadcast.id} created and queued")
    
    return broadcast


@router.get("", response_model=List[BroadcastResponse])
def list_broadcasts(
    limit: int = 50,
    session: Session = Depends(get_session)
):
    """List all broadcasts."""
    broadcasts = session.exec(
        select(Broadcast)
        .order_by(Broadcast.created_at.desc())
        .limit(limit)
    ).all()
    return broadcasts


@router.get("/{broadcast_id}", response_model=BroadcastResponse)
def get_broadcast(
    broadcast_id: int,
    session: Session = Depends(get_session)
):
    """Get broadcast by ID."""
    broadcast = session.get(Broadcast, broadcast_id)
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    return broadcast

