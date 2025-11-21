"""WhatsApp webhook endpoints."""
from fastapi import APIRouter, Request, HTTPException, Query
from app.services.whatsapp_service import handle_incoming_webhook
from app.core.config import settings
from app.core.logging import logger

router = APIRouter(prefix="/webhook", tags=["whatsapp"])


@router.get("")
async def verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """WhatsApp webhook verification endpoint."""
    logger.info("Verification request received:")
    logger.info(f"  hub.mode: {hub_mode}")
    logger.info(f"  hub.challenge: {hub_challenge}")
    logger.info(f"  hub.verify_token: {hub_verify_token}")
    logger.info(f"  Expected token: {settings.WHATSAPP_VERIFY_TOKEN}")
    
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("✅ Webhook verified successfully!")
        return int(hub_challenge)
    
    logger.warning("❌ Webhook verification failed!")
    logger.warning(f"   Received: '{hub_verify_token}'")
    logger.warning(f"   Expected: '{settings.WHATSAPP_VERIFY_TOKEN}'")
    logger.warning("   💡 Make sure WHATSAPP_VERIFY_TOKEN in .env matches your WhatsApp dashboard!")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def receive(request: Request):
    """WhatsApp webhook message receiver."""
    payload = await request.json()
    logger.info("📱 Received webhook payload")
    await handle_incoming_webhook(payload)
    return {"status": "ok"}

