"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging import logger
from app.db.init_db import init_db
from app.tools.registry import init_tools
from app.api.routes import whatsapp, admin, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting WhatsApp Bot...")
    
    # Initialize database
    init_db()
    
    # Initialize tools
    init_tools()
    logger.info("Tools initialized")
    
    yield
    
    logger.info("Shutting down WhatsApp Bot...")


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan
)

# CORS middleware for admin panel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your admin panel domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(whatsapp.router)
app.include_router(admin.router)


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


