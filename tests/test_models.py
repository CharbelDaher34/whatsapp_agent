"""Tests for database models."""
import pytest
from datetime import datetime
from sqlmodel import Session

from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message


def test_create_user(session: Session):
    """Test creating a user."""
    user = User(
        phone="1234567890",
        display_name="Test User",
        subscription_tier="free",
        is_active=True
    )
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    assert user.id is not None
    assert user.phone == "1234567890"
    assert user.subscription_tier == "free"
    assert user.is_active is True
    assert isinstance(user.created_at, datetime)


def test_create_conversation(session: Session):
    """Test creating a conversation."""
    # Create user first
    user = User(phone="1234567890")
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Create conversation
    conversation = Conversation(
        user_id=user.id,
        status="active"
    )
    
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    
    assert conversation.id is not None
    assert conversation.user_id == user.id
    assert conversation.status == "active"


def test_create_message(session: Session):
    """Test creating a message."""
    # Create user and conversation
    user = User(phone="1234567890")
    session.add(user)
    session.commit()
    session.refresh(user)
    
    conversation = Conversation(user_id=user.id)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    
    # Create message
    message = Message(
        conversation_id=conversation.id,
        sender="user",
        msg_type="text",
        content="Hello, bot!"
    )
    
    session.add(message)
    session.commit()
    session.refresh(message)
    
    assert message.id is not None
    assert message.conversation_id == conversation.id
    assert message.sender == "user"
    assert message.content == "Hello, bot!"


def test_user_subscription_tiers():
    """Test user subscription tier validation."""
    valid_tiers = ["free", "plus", "pro"]
    
    for tier in valid_tiers:
        user = User(phone="test", subscription_tier=tier)
        assert user.subscription_tier == tier

