"""ARQ worker entry point."""
import asyncio
from arq.worker import create_worker
from arq.connections import RedisSettings
from app.core.config import settings
from app.core.logging import logger
from app.queue.tasks import WorkerSettings
from app.db.init_db import init_db
from app.tools.registry import init_tools


async def main():
    """
    Start ARQ worker.
    
    Run this with:
        uv run python -m app.queue.worker
    
    Or use ARQ's CLI:
        uv run arq app.queue.tasks.WorkerSettings
    """
    # Initialize database tables (async)
    from app.db.init_db import init_db_async
    try:
        await init_db_async()
        logger.info("Database initialized for worker (async)")
    except Exception as e:
        logger.warning(f"Async DB init failed, falling back to sync: {e}")
        init_db()
        logger.info("Database initialized for worker (sync)")
    
    # Initialize tools registry
    init_tools()
    logger.info("Tools registry initialized for worker")
    
    # Parse Redis URL
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    
    # Update worker settings with Redis config
    WorkerSettings.redis_settings = redis_settings
    
    logger.info("🚀 Starting ARQ worker...")
    logger.info(f"   Redis: {settings.REDIS_URL}")
    logger.info(f"   Queue: {WorkerSettings.queue_name}")
    logger.info(f"   Max jobs: {WorkerSettings.max_jobs}")
    logger.info(f"   Job timeout: {WorkerSettings.job_timeout}s")
    logger.info(f"   Max retries: {WorkerSettings.max_tries}")
    
    # Create and run worker
    worker = create_worker(WorkerSettings)
    await worker.main()


if __name__ == "__main__":
    asyncio.run(main())

