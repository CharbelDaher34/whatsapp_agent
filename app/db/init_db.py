"""Database initialization."""
from sqlmodel import SQLModel
from app.db.session import engine
from app.models import User, Conversation, Message, ToolConfig
from app.core.logging import logger


def init_db():
    """Create all tables."""
    logger.info("Creating database tables...")
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created successfully")


