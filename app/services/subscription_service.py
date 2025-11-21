"""Subscription service for managing user subscriptions and usage."""
from app.models.user import User


def can_user_send_message(user: User) -> bool:
    """
    Check if user can send messages based on subscription and usage.
    Currently mock implementation - always allows if user is active.
    TODO: Add real usage tracking with a Usage table.
    """
    return user.is_active


def register_usage(user: User) -> None:
    """
    Register a message usage for the user.
    Currently mock implementation.
    TODO: Increment usage in a Usage table and enforce limits.
    """
    pass


