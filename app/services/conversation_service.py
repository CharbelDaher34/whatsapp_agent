"""Conversation flow and state management service."""
from typing import Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlmodel import SQLModel
from pydantic import BaseModel
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.core.logging import logger
from app.core.exceptions import ConversationError


class ConversationContext(BaseModel):
    """Context for a conversation including history."""
    conversation: Conversation
    history: List[Message]
    user: User


async def get_or_create_user_conversation(
    phone: str,
    session: AsyncSession
) -> Tuple[User, Conversation]:
    """
    Get or create user and their active conversation.
    Handles race conditions with concurrent creates.
    
    Args:
        phone: User's phone number
        session: Database session
        
    Returns:
        Tuple of (User, Conversation)
        
    Raises:
        ConversationError: If database operations fail
    """
    from sqlalchemy.exc import IntegrityError
    
    try:
        # Get or create user
        result = await session.execute(
            select(User).where(User.phone == phone)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            try:
                user = User(
                    phone=phone,
                    subscription_tier="free"
                )
                session.add(user)
                await session.flush()  # Get user.id
                logger.info(f"Created new user: {phone}")
            except IntegrityError:
                # Race condition: another worker created the user
                # Rollback and re-query
                await session.rollback()
                result = await session.execute(
                    select(User).where(User.phone == phone)
                )
                user = result.scalar_one()
                logger.info(f"User already exists (race condition): {phone}")
        
        # Get or create active conversation
        result = await session.execute(
            select(Conversation).where(
                Conversation.user_id == user.id,
                Conversation.status == "active"
            ).order_by(Conversation.created_at.desc())
        )
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            try:
                conversation = Conversation(
                    user_id=user.id,
                    status="active"
                )
                session.add(conversation)
                await session.flush()  # Get conversation.id
                logger.info(f"Created new conversation for user {phone}")
            except IntegrityError:
                # Race condition: another worker created the conversation
                # Rollback and re-query
                await session.rollback()
                result = await session.execute(
                    select(Conversation).where(
                        Conversation.user_id == user.id,
                        Conversation.status == "active"
                    ).order_by(Conversation.created_at.desc())
                )
                conversation = result.scalar_one()
                logger.info(f"Conversation already exists (race condition): {phone}")
        
        return user, conversation
        
    except Exception as e:
        logger.error(f"Error getting/creating user conversation: {e}")
        raise ConversationError(f"Failed to get/create conversation: {e}")


async def save_user_message(
    conversation_id: int,
    content: str,
    msg_type: str,
    session: AsyncSession
) -> Message:
    """
    Save a user message to the database.
    
    Args:
        conversation_id: Conversation ID
        content: Message content
        msg_type: Message type
        session: Database session
        
    Returns:
        Created Message object
    """
    try:
        message = Message(
            conversation_id=conversation_id,
            sender="user",
            msg_type=msg_type,
            content=content
        )
        session.add(message)
        await session.flush()
        logger.debug(f"Saved user message to conversation {conversation_id}")
        return message
    except Exception as e:
        logger.error(f"Error saving user message: {e}")
        raise ConversationError(f"Failed to save user message: {e}")


async def save_bot_message(
    conversation_id: int,
    content: str,
    msg_type: str,
    session: AsyncSession
) -> Message:
    """
    Save a bot message to the database.
    
    Args:
        conversation_id: Conversation ID
        content: Message content
        msg_type: Message type
        session: Database session
        
    Returns:
        Created Message object
    """
    try:
        message = Message(
            conversation_id=conversation_id,
            sender="assistant",
            msg_type=msg_type,
            content=content
        )
        session.add(message)
        await session.flush()
        logger.debug(f"Saved bot message to conversation {conversation_id}")
        return message
    except Exception as e:
        logger.error(f"Error saving bot message: {e}")
        raise ConversationError(f"Failed to save bot message: {e}")


async def get_conversation_context(
    conversation: Conversation,
    session: AsyncSession,
    limit: int = 20
) -> ConversationContext:
    """
    Get conversation context including history.
    
    Args:
        conversation: Conversation object
        session: Database session
        limit: Maximum number of messages to retrieve
        
    Returns:
        ConversationContext with history
    """
    try:
        # Get conversation history
        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        messages.reverse()  # Chronological order
        
        # Get user
        result = await session.execute(
            select(User).where(User.id == conversation.user_id)
        )
        user = result.scalar_one()
        
        return ConversationContext(
            conversation=conversation,
            history=messages,
            user=user
        )
    except Exception as e:
        logger.error(f"Error getting conversation context: {e}")
        raise ConversationError(f"Failed to get context: {e}")


async def close_conversation(
    conversation_id: int,
    session: AsyncSession
) -> None:
    """
    Close an active conversation.
    
    Args:
        conversation_id: Conversation ID
        session: Database session
    """
    try:
        result = await session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        
        if conversation:
            conversation.status = "closed"
            await session.flush()
            logger.info(f"Closed conversation {conversation_id}")
    except Exception as e:
        logger.error(f"Error closing conversation: {e}")
        raise ConversationError(f"Failed to close conversation: {e}")

