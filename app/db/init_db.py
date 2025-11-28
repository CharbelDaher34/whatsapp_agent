"""Database initialization."""
from sqlmodel import SQLModel
from app.db.session import async_engine, sync_engine
from app.models import User, Conversation, Message, ToolConfig
from app.models.interaction import Interaction
from app.models.webhook_log import WebhookLog
from app.models.broadcast import Broadcast
from app.core.logging import logger


async def init_db_async(delete_existing: bool = False):
    """Create all tables asynchronously. If delete_existing is True, delete all tables first."""
    if delete_existing:
        logger.info("Deleting existing database tables (async)...")
        async with async_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
        logger.info("Existing database tables deleted successfully")

    logger.info("Creating database tables (async)...")
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("Database tables created successfully")


def init_db():
    """Create all tables synchronously (for backward compatibility)."""
    logger.info("Creating database tables (sync)...")
    SQLModel.metadata.create_all(sync_engine)
    logger.info("Database tables created successfully")


