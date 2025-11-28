"""Tests for webhook security."""
import pytest
from app.utils.whatsapp_security import (
    verify_webhook_signature,
    validate_verify_token
)


def test_validate_verify_token_success():
    """Test verify token validation with matching tokens."""
    token = "test_token_123"
    assert validate_verify_token(token, token) is True


def test_validate_verify_token_failure():
    """Test verify token validation with mismatched tokens."""
    received = "wrong_token"
    expected = "correct_token"
    assert validate_verify_token(received, expected) is False


def test_validate_verify_token_empty():
    """Test verify token validation with empty tokens."""
    assert validate_verify_token("", "token") is False
    assert validate_verify_token("token", "") is False
    assert validate_verify_token("", "") is False


def test_verify_webhook_signature_valid():
    """Test webhook signature verification with valid signature."""
    payload = b'{"test": "data"}'
    app_secret = "test_secret"
    
    # Calculate expected signature
    import hmac
    import hashlib
    signature_hash = hmac.new(
        app_secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    signature = f"sha256={signature_hash}"
    
    assert verify_webhook_signature(payload, signature, app_secret) is True


def test_verify_webhook_signature_invalid():
    """Test webhook signature verification with invalid signature."""
    payload = b'{"test": "data"}'
    app_secret = "test_secret"
    invalid_signature = "sha256=invalid_hash"
    
    assert verify_webhook_signature(payload, invalid_signature, app_secret) is False


def test_verify_webhook_signature_missing():
    """Test webhook signature verification with missing signature."""
    payload = b'{"test": "data"}'
    app_secret = "test_secret"
    
    assert verify_webhook_signature(payload, "", app_secret) is False
    assert verify_webhook_signature(payload, None, app_secret) is False

