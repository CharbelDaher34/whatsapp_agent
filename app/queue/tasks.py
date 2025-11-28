"""Background tasks for async processing."""
from typing import Dict, Any
from app.services.whatsapp_service import handle_incoming_webhook
from app.core.logging import logger


async def process_webhook_message(ctx: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, str]:
    """
    Process WhatsApp webhook message in background.
    """
    job_id = ctx.get('job_id')
    try:
        logger.info(f"🔄 [Job {job_id}] Processing webhook message in background")
        logger.info(f"📦 [Job {job_id}] Payload keys: {list(payload.keys())}")
        
        # Process the webhook
        result = await handle_incoming_webhook(payload)
        
        logger.info(f"✅ [Job {job_id}] Webhook processed successfully")
        logger.info(f"📤 [Job {job_id}] Result: {result}")
        return {"status": "success", "data": result}
        
    except Exception as e:
        logger.error(f"❌ [Job {job_id}] Error processing webhook: {e}", exc_info=True)
        raise


async def startup(ctx: Dict[str, Any]) -> None:
    """
    Worker startup function.
    Called when ARQ worker starts.
    """
    logger.info("🚀 ARQ worker starting up...")
    # Initialize any resources needed by workers
    # (database connections are created per-request)


async def shutdown(ctx: Dict[str, Any]) -> None:
    """
    Worker shutdown function.
    Called when ARQ worker shuts down.
    """
    logger.info("👋 ARQ worker shutting down...")
    # Cleanup resources


# ARQ Worker Class Configuration
class WorkerSettings:
    """
    ARQ worker settings.
    
    See: https://arq-docs.helpmanual.io/
    """
    
    functions = [process_webhook_message]
    
    on_startup = startup
    on_shutdown = shutdown
    
    # Redis connection
    redis_settings = None  # Will be set from config at runtime
    
    # Job settings
    max_jobs = 10  # Max concurrent jobs per worker
    job_timeout = 300  # 5 minutes max per job
    
    # Retry settings
    max_tries = 3  # Retry failed jobs up to 3 times
    retry_jobs = True
    
    # Queue settings
    queue_name = "whatsapp:webhook"
    
    # Health check
    health_check_interval = 60

