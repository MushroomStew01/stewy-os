from datetime import UTC, datetime

import httpx
import pytest

from app.integrations.calories import CalorieIntegration
from app.integrations.lexus import LexusIntegration
from app.integrations.movies import MovieIntegration


@pytest.mark.asyncio
async def test_lexus_adapter_maps_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "ready": True,
                "fuel_percent": 82,
                "range_km": 351,
                "odometer_km": 54678,
                "vehicle": {"display_name": "2023 IS", "make": "Lexus"},
            },
        )

    integration = LexusIntegration("http://lexus.test", 2, transport=httpx.MockTransport(handler))
    snapshot = await integration.snapshot()
    assert snapshot.healthy is True
    assert snapshot.metrics["fuel_percent"] == 82
    assert snapshot.detail == "2023 IS"


@pytest.mark.asyncio
async def test_calorie_adapter_sends_api_key_and_maps_summary() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-API-Key") == "secret"
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "date": "2026-08-15",
                "meal_count": 3,
                "calories": 1540,
                "calorie_goal": 2000,
                "calories_remaining": 460,
                "protein": 104,
                "carbs": 180,
                "fat": 55,
            },
        )

    integration = CalorieIntegration(
        "http://calories.test",
        "secret",
        2,
        transport=httpx.MockTransport(handler),
    )
    snapshot = await integration.snapshot()
    assert snapshot.healthy is True
    assert snapshot.metrics["calories_remaining"] == 460
    assert snapshot.metrics["progress_percent"] == 77.0


@pytest.mark.asyncio
async def test_movie_adapter_maps_priority_status() -> None:
    now = datetime.now(UTC).isoformat()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "schema_version": 1,
                "updated_at": now,
                "state_id": "abc123",
                "healthy": True,
                "theatre_count": 4,
                "failing_targets": [],
                "priority_titles": ["Dune: Part 3"],
                "priority": {
                    "Dune: Part 3": {
                        "ticket_available": True,
                        "theatres": ["Kitchener", "Cambridge"],
                        "showtimes": ["7:00 pm", "10:15 pm"],
                        "dates": ["Dec 18"],
                        "formats": ["IMAX"],
                    }
                },
            },
        )

    integration = MovieIntegration(
        "https://status.test/status.json",
        2,
        36,
        transport=httpx.MockTransport(handler),
    )
    snapshot = await integration.snapshot()
    assert snapshot.healthy is True
    assert snapshot.status == "online"
    assert snapshot.metrics["ticket_available"] is True
    assert snapshot.metrics["theatres_found"] == 2
    assert snapshot.metrics["showtime_count"] == 2
    assert snapshot.metrics["state_id"] == "abc123"
