"""FastAPI application entry point."""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import (
    WhatsAppBotError,
    RateLimitExceeded,
    MediaProcessingError,
    AIGenerationError,
    ParseError,
    ConversationError
)
from app.db.init_db import init_db
from app.tools.registry import init_tools
from app.api.routes import whatsapp, admin, health, broadcast, webhooks_admin
from app.middleware import RateLimitMiddleware
from app.middleware.message_queue import MessageQueueMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting WhatsApp Bot...")
    
    # Initialize database (async)
    from app.db.init_db import init_db_async
    try:
        await init_db_async(delete_existing=False)
    except Exception as e:
        logger.warning(f"Async DB init failed, falling back to sync: {e}")
        init_db()
    
    # Initialize tools
    init_tools()
    logger.info("Tools initialized")
    
    # Initialize Redis (optional, will connect on first use)
    try:
        from app.queue.connection import get_redis_pool
        await get_redis_pool()
    except Exception as e:
        logger.warning(f"Redis connection failed (queue features disabled): {e}")
        logger.warning("Webhooks will be processed synchronously without queue")
    
    yield
    
    # Cleanup
    try:
        from app.queue.connection import close_redis_connections
        await close_redis_connections()
    except Exception:
        pass
    
    # Close async engine
    from app.db.session import async_engine
    await async_engine.dispose()
    
    logger.info("Shutting down WhatsApp Bot...")


app = FastAPI(
    title=settings.APP_NAME,
    description="""
    # WhatsApp Bot API
    
    A production-ready WhatsApp bot backend with AI-powered responses, 
    interactive messaging, and comprehensive admin controls.
    
    ## Features
    
    - 🤖 **AI-Powered Conversations**: OpenAI GPT-4o with context-aware responses
    - 🔐 **Secure**: Webhook signature verification, rate limiting, API key auth
    - 📱 **Interactive Messages**: Buttons, lists, reactions, typing indicators
    - 🎨 **Image Generation**: Text-to-image and image-to-image with Gemini API
    - 📊 **Analytics**: Real-time stats, webhook logs, user engagement metrics
    - 📢 **Broadcast**: Send messages to user segments
    - ⚙️ **Admin Panel**: Full control over users, tools, and system settings
    - 🔄 **Async Queue**: Redis-backed job queue for reliable processing
    
    ## Authentication
    
    - **Webhook endpoints**: Verified with X-Hub-Signature-256 header
    - **Admin endpoints**: Require X-Admin-Key header
    
    ## Rate Limits
    
    - Global: 60 requests/minute per IP
    - WhatsApp API: 1000 messages/second (enforced by WhatsApp)
    
    ## Quick Start
    
    1. Set up your `.env` file with required credentials
    2. Start Redis: `redis-server`
    3. Start API: `uv run uvicorn app.main:app --reload`
    4. Start worker: `uv run python -m app.queue.worker`
    5. Configure webhook in WhatsApp dashboard
    """,
    version="0.1.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "health",
            "description": "Health check and monitoring endpoints"
        },
        {
            "name": "whatsapp",
            "description": "WhatsApp webhook endpoints for receiving messages"
        },
        {
            "name": "admin",
            "description": "Admin endpoints for managing users, tools, and system (requires X-Admin-Key)"
        },
        {
            "name": "broadcast",
            "description": "Broadcast messaging endpoints (requires X-Admin-Key)"
        },
        {
            "name": "webhooks",
            "description": "Webhook logs and monitoring (requires X-Admin-Key)"
        }
    ]
)

# Message queue middleware (add first for user-level queuing)
if settings.USER_QUEUE_ENABLED:
    app.add_middleware(MessageQueueMiddleware)
    logger.info(f"User message queue enabled (TTL: {settings.USER_QUEUE_TTL}s, Max: {settings.USER_QUEUE_MAX_SIZE})")

# Rate limiting middleware (add second for early rejection)
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimitMiddleware)
    logger.info("Rate limiting enabled")

# CORS middleware for admin panel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your admin panel domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handlers
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceptions."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"error": "Rate limit exceeded", "detail": str(exc)}
    )


@app.exception_handler(MediaProcessingError)
async def media_error_handler(request: Request, exc: MediaProcessingError):
    """Handle media processing errors."""
    logger.error(f"Media processing error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Media processing failed", "detail": str(exc)}
    )


@app.exception_handler(AIGenerationError)
async def ai_error_handler(request: Request, exc: AIGenerationError):
    """Handle AI generation errors."""
    logger.error(f"AI generation error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "AI generation failed", "detail": str(exc)}
    )


@app.exception_handler(ParseError)
async def parse_error_handler(request: Request, exc: ParseError):
    """Handle parsing errors."""
    logger.error(f"Parse error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Invalid payload", "detail": str(exc)}
    )


@app.exception_handler(ConversationError)
async def conversation_error_handler(request: Request, exc: ConversationError):
    """Handle conversation errors."""
    logger.error(f"Conversation error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Conversation error", "detail": str(exc)}
    )


@app.exception_handler(WhatsAppBotError)
async def whatsapp_bot_error_handler(request: Request, exc: WhatsAppBotError):
    """Handle general WhatsApp bot errors."""
    logger.error(f"WhatsApp bot error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "WhatsApp bot error", "detail": str(exc)}
    )


# Include routers
app.include_router(health.router)
app.include_router(whatsapp.router)
app.include_router(admin.router)
app.include_router(broadcast.router)
app.include_router(webhooks_admin.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "WhatsApp Bot API",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )


