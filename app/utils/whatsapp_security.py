"""WhatsApp webhook security utilities."""
import hmac
import hashlib
from typing import Optional
from app.core.logging import logger


def verify_webhook_signature(payload: bytes, signature: str, app_secret: str) -> bool:
    """
    Verify WhatsApp webhook signature.
    
    According to WhatsApp Cloud API documentation:
    https://developers.facebook.com/docs/whatsapp/cloud-api/guides/set-up-webhooks
    
    WhatsApp signs webhook payloads with SHA256 HMAC and sends the signature
    in the X-Hub-Signature-256 header.
    
    Args:
        payload: Raw request body as bytes
        signature: The X-Hub-Signature-256 header value
        app_secret: Your app secret from Meta dashboard
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not signature or not app_secret:
        logger.warning("Missing signature or app secret")
        return False
    
    # WhatsApp sends signature as "sha256=<signature>"
    if not signature.startswith("sha256="):
        logger.warning(f"Invalid signature format: {signature}")
        return False
    
    # Extract the signature hash
    expected_signature = signature.split("sha256=")[1]
    
    # Calculate the expected signature
    calculated_signature = hmac.new(
        app_secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures using constant-time comparison to prevent timing attacks
    is_valid = hmac.compare_digest(calculated_signature, expected_signature)
    
    if not is_valid:
        logger.warning("Webhook signature verification failed")
        logger.debug(f"Expected: {calculated_signature[:10]}...")
        logger.debug(f"Received: {expected_signature[:10]}...")
    
    return is_valid


def validate_verify_token(received_token: str, expected_token: str) -> bool:
    """
    Validate webhook verification token.
    
    Args:
        received_token: Token received in hub.verify_token parameter
        expected_token: Your configured verify token
        
    Returns:
        True if tokens match, False otherwise
    """
    if not received_token or not expected_token:
        return False
    
    return hmac.compare_digest(received_token, expected_token)

