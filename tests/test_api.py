"""Tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient


def test_root_endpoint_renders_landing(client: TestClient):
    """The root path now serves the marketing landing HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "WhatsApp" in response.text


def test_pricing_page_lists_plans(client: TestClient):
    response = client.get("/pricing")
    assert response.status_code == 200
    body = response.text
    for plan in ("Free", "Pro", "Max"):
        assert plan in body


def test_login_page_renders(client: TestClient):
    response = client.get("/login")
    assert response.status_code == 200
    assert "WhatsApp" in response.text


def test_admin_ui_page_renders(client: TestClient):
    response = client.get("/admin-ui")
    assert response.status_code == 200
    assert "Admin Panel" in response.text


def test_dashboard_requires_auth(client: TestClient):
    response = client.get("/dashboard")
    assert response.status_code == 401


def test_api_index_returns_json(client: TestClient):
    response = client.get("/api")
    assert response.status_code == 200
    assert "app" in response.json()


def test_health_endpoint(client: TestClient):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


def test_webhook_verification_success(client: TestClient):
    """Test webhook verification with correct token."""
    from app.core.config import settings
    
    response = client.get("/webhook", params={
        "hub.mode": "subscribe",
        "hub.challenge": "12345",
        "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN
    })
    
    assert response.status_code == 200
    assert response.json() == 12345


def test_webhook_verification_failure(client: TestClient):
    """Test webhook verification with incorrect token."""
    response = client.get("/webhook", params={
        "hub.mode": "subscribe",
        "hub.challenge": "12345",
        "hub.verify_token": "wrong_token"
    })
    
    assert response.status_code == 403


def test_admin_auth_required(client: TestClient):
    """Test that admin endpoints require authentication."""
    response = client.get("/admin/users")
    assert response.status_code in [401, 403]


def test_admin_stats_with_auth(client: TestClient):
    """Test admin stats endpoint with valid auth."""
    from app.core.config import settings
    
    response = client.get(
        "/admin/stats",
        headers={"X-Admin-Key": settings.ADMIN_API_KEY}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "total_users" in data
    assert "total_messages" in data

