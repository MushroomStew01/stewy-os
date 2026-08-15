import httpx
import pytest

from app.integrations.calories import CalorieIntegration
from app.integrations.lexus import LexusIntegration


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
                "vehicle": "2023 IS",
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
