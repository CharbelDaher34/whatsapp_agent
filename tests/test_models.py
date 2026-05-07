"""Tests for database models."""
from datetime import datetime

import pytest
from sqlmodel import Session

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import SUBSCRIPTION_TIERS, User


def test_create_user(session: Session):
    user = User(
        phone="1234567890",
        display_name="Test User",
        subscription_tier="free",
        is_active=True,
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
    user = User(phone="1234567890")
    session.add(user)
    session.commit()
    session.refresh(user)

    conversation = Conversation(user_id=user.id, status="active")
    session.add(conversation)
    session.commit()
    session.refresh(conversation)

    assert conversation.id is not None
    assert conversation.user_id == user.id
    assert conversation.status == "active"


def test_create_message(session: Session):
    user = User(phone="1234567890")
    session.add(user)
    session.commit()
    session.refresh(user)

    conversation = Conversation(user_id=user.id)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)

    message = Message(
        conversation_id=conversation.id,
        sender="user",
        msg_type="text",
        content="Hello, bot!",
    )
    session.add(message)
    session.commit()
    session.refresh(message)

    assert message.id is not None
    assert message.conversation_id == conversation.id
    assert message.sender == "user"
    assert message.content == "Hello, bot!"


@pytest.mark.parametrize("tier", SUBSCRIPTION_TIERS)
def test_user_subscription_tiers(tier):
    user = User(phone="test", subscription_tier=tier)
    assert user.subscription_tier == tier
    assert tier in ("free", "pro", "max")
