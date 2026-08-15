from fastapi.testclient import TestClient

from app.main import app


def test_healthz() -> None:
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_api_contains_system() -> None:
    with TestClient(app) as client:
        response = client.get("/api/dashboard?force=true")
    assert response.status_code == 200
    payload = response.json()
    assert "system" in payload["integrations"]
    assert payload["integrations"]["system"]["healthy"] is True


def test_dashboard_page_renders() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Stewy OS" in response.text
    assert "RECENT ACTIVITY" in response.text
