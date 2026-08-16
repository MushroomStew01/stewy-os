import pytest
from fastapi.testclient import TestClient

from app.integrations.system import SystemIntegration
from app.main import app, dashboard_service


@pytest.fixture(autouse=True)
def isolate_dashboard_integrations():
    original = dashboard_service.integrations
    original_cache = dashboard_service._cache
    original_cache_at = dashboard_service._cache_at
    dashboard_service.integrations = [SystemIntegration()]
    dashboard_service._cache = None
    dashboard_service._cache_at = 0.0
    try:
        yield
    finally:
        dashboard_service.integrations = original
        dashboard_service._cache = original_cache
        dashboard_service._cache_at = original_cache_at


def test_healthz() -> None:
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_api_contains_system_and_notifications() -> None:
    with TestClient(app) as client:
        response = client.get("/api/dashboard?force=true")
    assert response.status_code == 200
    payload = response.json()
    assert "system" in payload["integrations"]
    assert payload["integrations"]["system"]["healthy"] is True
    assert payload["notifications"]["status"] == "disabled"


def test_notifications_api_returns_history_list() -> None:
    with TestClient(app) as client:
        response = client.get("/api/notifications")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_dashboard_page_renders() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Stewy OS" in response.text
    assert "RECENT ACTIVITY" in response.text
    assert "HOME" in response.text
    assert "Home Assistant" in response.text
    assert "GitHub Actions" in response.text
    assert "Docker" in response.text
    assert "NOTIFICATIONS" in response.text
