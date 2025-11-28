"""WhatsApp webhook endpoints with security and validation."""
from fastapi import APIRouter, Request, HTTPException, Query, Header, status
from typing import Optional
from app.services.whatsapp_service import handle_incoming_webhook
from app.core.config import settings
from app.core.logging import logger
from app.utils.whatsapp_security import verify_webhook_signature, validate_verify_token
from app.schemas.whatsapp import WebhookPayload, VerificationRequest
from pydantic import ValidationError

router = APIRouter(prefix="/webhook", tags=["whatsapp"])


@router.get("")
async def verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """
    WhatsApp webhook verification endpoint.
    
    This endpoint is called by WhatsApp when you set up the webhook.
    It verifies that you control the endpoint by validating the verify token.
    
    Reference: https://developers.facebook.com/docs/whatsapp/cloud-api/guides/set-up-webhooks
    """
    logger.info("🔍 Verification request received:")
    logger.info(f"  hub.mode: {hub_mode}")
    logger.info(f"  hub.challenge: {hub_challenge}")
    logger.info(f"  hub.verify_token: {hub_verify_token[:10]}..." if hub_verify_token else "  hub.verify_token: None")
    logger.info(f"  Expected token: {settings.WHATSAPP_VERIFY_TOKEN[:10]}...")
    
    # Validate parameters
    if not hub_mode or not hub_challenge or not hub_verify_token:
        logger.warning("❌ Missing required parameters")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required parameters"
        )
    
    # Verify mode is "subscribe"
    if hub_mode != "subscribe":
        logger.warning(f"❌ Invalid hub.mode: {hub_mode}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid hub.mode, expected 'subscribe'"
        )
    
    # Validate verify token using constant-time comparison
    if not validate_verify_token(hub_verify_token, settings.WHATSAPP_VERIFY_TOKEN):
        logger.warning("❌ Webhook verification failed!")
        logger.warning(f"   Received token: '{hub_verify_token[:10]}...'")
        logger.warning(f"   Expected token: '{settings.WHATSAPP_VERIFY_TOKEN[:10]}...'")
        logger.warning("   💡 Make sure WHATSAPP_VERIFY_TOKEN in .env matches your WhatsApp dashboard!")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verification failed"
        )
    
    # Return challenge to complete verification
        logger.info("✅ Webhook verified successfully!")
    try:
        return int(hub_challenge)
    except ValueError:
        logger.error(f"Invalid challenge format: {hub_challenge}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid challenge format"
        )


@router.post("")
async def receive(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256")
):
    """
    WhatsApp webhook message receiver.
    
    This endpoint receives incoming WhatsApp messages and events.
    It verifies the webhook signature for security and validates the payload structure.
    
    Security:
    - Verifies X-Hub-Signature-256 header (HMAC SHA256 signature)
    - Validates payload structure with Pydantic schemas
    - Rate limited by middleware
    
    Reference: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        
        # Verify webhook signature if app secret is configured
        if settings.WHATSAPP_APP_SECRET:
            if not x_hub_signature_256:
                logger.error("❌ Missing X-Hub-Signature-256 header")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing signature header"
                )
            
            if not verify_webhook_signature(
                body, 
                x_hub_signature_256, 
                settings.WHATSAPP_APP_SECRET
            ):
                logger.error("❌ Invalid webhook signature")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid signature"
                )
            
            logger.debug("✅ Webhook signature verified")
        else:
            logger.warning("⚠️  WHATSAPP_APP_SECRET not configured - signature verification skipped")
            logger.warning("   This is a security risk in production!")
        
        # Parse and validate payload
        try:
            payload_dict = await request.json()
            payload = WebhookPayload(**payload_dict)
            logger.info("✅ Webhook payload validated")
        except ValidationError as e:
            logger.error(f"❌ Invalid webhook payload structure: {e}")
            logger.debug(f"Raw payload: {body.decode('utf-8')[:500]}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid payload structure: {str(e)}"
            )
        except Exception as e:
            logger.error(f"❌ Failed to parse webhook payload: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to parse payload"
            )
        
        # Log webhook event
        logger.info("📱 Received webhook payload")
        logger.debug(f"Object: {payload.object}")
        logger.debug(f"Entries: {len(payload.entry)}")
        
        # Try to enqueue webhook for async processing
        try:
            from app.queue.connection import get_arq_redis
            
            arq_redis = await get_arq_redis()
            job = await arq_redis.enqueue_job(
                'process_webhook_message',
                payload_dict,
                _queue_name='whatsapp:webhook'
            )
            logger.info(f"✅ Webhook enqueued for processing (job_id: {job.job_id})")
            
        except Exception as e:
            # Fallback to synchronous processing if queue is unavailable
            logger.warning(f"Queue unavailable, processing synchronously: {e}")
            logger.error(f"Error details: {e}", exc_info=True)
            await handle_incoming_webhook(payload_dict)
        
        # Return success response immediately (message will be processed async)
        return {"status": "ok"}
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Catch any unexpected errors
        logger.error(f"❌ Unexpected error processing webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error processing webhook"
        )

