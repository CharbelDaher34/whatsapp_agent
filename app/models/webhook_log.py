"""Webhook log model for tracking all webhook events."""
from sqlmodel import SQLModel, Field, Column, JSON
from typing import Optional, Dict, Any
from datetime import datetime


class WebhookLog(SQLModel, table=True):
    """Log all incoming webhook events for debugging and monitoring."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Webhook details
    event_type: str  # "message", "status", "unknown"
    phone_number: Optional[str] = None  # User's phone number
    message_id: Optional[str] = None  # WhatsApp message ID
    
    # Status
    status: str  # "received", "processing", "success", "failed"
    error_message: Optional[str] = None
    
    # Raw payload
    payload: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    
    # Response
    response_time_ms: Optional[int] = None
    
    # Timestamps
    received_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

