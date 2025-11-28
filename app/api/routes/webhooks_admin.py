"""Admin endpoints for webhook logs and monitoring."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.db.session import get_session
from app.models.webhook_log import WebhookLog
from app.utils.auth import admin_auth


router = APIRouter(
    prefix="/admin/webhooks",
    tags=["admin", "webhooks"],
    dependencies=[Depends(admin_auth)]
)


class WebhookLogResponse(BaseModel):
    """Webhook log response."""
    id: int
    event_type: str
    phone_number: Optional[str]
    message_id: Optional[str]
    status: str
    error_message: Optional[str]
    response_time_ms: Optional[int]
    received_at: datetime
    processed_at: Optional[datetime]


class WebhookStats(BaseModel):
    """Webhook statistics."""
    total_events: int
    success_count: int
    failed_count: int
    average_response_time_ms: Optional[float]
    events_last_hour: int
    events_last_24h: int


@router.get("/logs", response_model=List[WebhookLogResponse])
def get_webhook_logs(
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    event_type: Optional[str] = None,
    phone_number: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """
    Get webhook logs with filtering.
    
    Query parameters:
    - limit: Max number of logs to return (default 50, max 500)
    - offset: Offset for pagination
    - status: Filter by status (received, processing, success, failed)
    - event_type: Filter by event type
    - phone_number: Filter by phone number
    """
    query = select(WebhookLog).order_by(WebhookLog.received_at.desc())
    
    if status:
        query = query.where(WebhookLog.status == status)
    
    if event_type:
        query = query.where(WebhookLog.event_type == event_type)
    
    if phone_number:
        query = query.where(WebhookLog.phone_number == phone_number)
    
    logs = session.exec(query.offset(offset).limit(limit)).all()
    
    return logs


@router.get("/logs/{log_id}")
def get_webhook_log(
    log_id: int,
    session: Session = Depends(get_session)
):
    """Get webhook log by ID with full payload."""
    log = session.get(WebhookLog, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Webhook log not found")
    return log


@router.get("/stats", response_model=WebhookStats)
def get_webhook_stats(session: Session = Depends(get_session)):
    """Get webhook statistics."""
    
    # Total events
    total_events = session.exec(select(func.count(WebhookLog.id))).one()
    
    # Success count
    success_count = session.exec(
        select(func.count(WebhookLog.id)).where(WebhookLog.status == "success")
    ).one()
    
    # Failed count
    failed_count = session.exec(
        select(func.count(WebhookLog.id)).where(WebhookLog.status == "failed")
    ).one()
    
    # Average response time
    avg_response_time = session.exec(
        select(func.avg(WebhookLog.response_time_ms))
        .where(WebhookLog.response_time_ms.isnot(None))
    ).one()
    
    # Events last hour
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    events_last_hour = session.exec(
        select(func.count(WebhookLog.id))
        .where(WebhookLog.received_at >= one_hour_ago)
    ).one()
    
    # Events last 24 hours
    one_day_ago = datetime.utcnow() - timedelta(hours=24)
    events_last_24h = session.exec(
        select(func.count(WebhookLog.id))
        .where(WebhookLog.received_at >= one_day_ago)
    ).one()
    
    return WebhookStats(
        total_events=total_events or 0,
        success_count=success_count or 0,
        failed_count=failed_count or 0,
        average_response_time_ms=float(avg_response_time) if avg_response_time else None,
        events_last_hour=events_last_hour or 0,
        events_last_24h=events_last_24h or 0
    )


@router.delete("/logs")
def clear_old_logs(
    days: int = Query(30, ge=1, le=365),
    session: Session = Depends(get_session)
):
    """
    Delete webhook logs older than specified days.
    
    Args:
        days: Delete logs older than this many days (default 30)
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Count logs to be deleted
    count = session.exec(
        select(func.count(WebhookLog.id))
        .where(WebhookLog.received_at < cutoff_date)
    ).one()
    
    # Delete old logs
    old_logs = session.exec(
        select(WebhookLog).where(WebhookLog.received_at < cutoff_date)
    ).all()
    
    for log in old_logs:
        session.delete(log)
    
    session.commit()
    
    return {
        "deleted": count or 0,
        "cutoff_date": cutoff_date.isoformat()
    }

