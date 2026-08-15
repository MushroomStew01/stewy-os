from datetime import UTC, datetime

import httpx
import pytest

from app.integrations.calories import CalorieIntegration
from app.integrations.home_assistant import HomeAssistantIntegration
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


@pytest.mark.asyncio
async def test_home_assistant_adapter_maps_presence_temperatures_and_selected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Bearer ha-secret"
        assert request.url.path == "/api/states"
        return httpx.Response(
            200,
            json=[
                {
                    "entity_id": "person.andy",
                    "state": "home",
                    "attributes": {"friendly_name": "Andy"},
                    "last_updated": "2026-08-15T23:00:00+00:00",
                },
                {
                    "entity_id": "sensor.living_room_temperature",
                    "state": "22.4",
                    "attributes": {
                        "friendly_name": "Living Room Temperature",
                        "device_class": "temperature",
                        "unit_of_measurement": "°C",
                    },
                    "last_updated": "2026-08-15T23:01:00+00:00",
                },
                {
                    "entity_id": "sensor.cpu_temperature",
                    "state": "44.1",
                    "attributes": {
                        "friendly_name": "CPU Temperature",
                        "device_class": "temperature",
                        "unit_of_measurement": "°C",
                    },
                },
                {
                    "entity_id": "binary_sensor.front_door",
                    "state": "off",
                    "attributes": {"friendly_name": "Front Door"},
                },
            ],
        )

    integration = HomeAssistantIntegration(
        "http://ha.test",
        "ha-secret",
        2,
        selected_entities="binary_sensor.front_door",
        transport=httpx.MockTransport(handler),
    )
    snapshot = await integration.snapshot()
    assert snapshot.healthy is True
    assert snapshot.status == "online"
    assert snapshot.metrics["people_home"] == 1
    assert snapshot.metrics["people_total"] == 1
    assert snapshot.metrics["temperature_count"] == 1
    assert snapshot.metrics["temperatures"][0]["name"] == "Living Room Temperature"
    assert snapshot.metrics["selected"][0]["state"] == "off"
    assert snapshot.metrics["entity_count"] == 4


@pytest.mark.asyncio
async def test_home_assistant_auto_presence_ignores_unknown_and_vehicle_trackers() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "entity_id": "person.lexushome",
                    "state": "unknown",
                    "attributes": {"friendly_name": "LexusHome"},
                },
                {
                    "entity_id": "device_tracker.andys_iphone",
                    "state": "unknown",
                    "attributes": {"friendly_name": "Andy’s iPhone"},
                },
                {
                    "entity_id": "device_tracker.2023_lexus_current_location",
                    "state": "not_home",
                    "attributes": {"friendly_name": "2023 Lexus Current Location"},
                },
                {
                    "entity_id": "device_tracker.2023_lexus_last_parked_location",
                    "state": "not_home",
                    "attributes": {"friendly_name": "2023 Lexus Last Parked Location"},
                },
            ],
        )

    integration = HomeAssistantIntegration(
        "http://ha.test",
        "ha-secret",
        2,
        transport=httpx.MockTransport(handler),
    )
    snapshot = await integration.snapshot()
    assert snapshot.metrics["people_home"] == 0
    assert snapshot.metrics["people_total"] == 0
    assert snapshot.metrics["presence"] == []


@pytest.mark.asyncio
async def test_home_assistant_auto_presence_falls_back_to_valid_device_tracker() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "entity_id": "person.lexushome",
                    "state": "unknown",
                    "attributes": {"friendly_name": "LexusHome"},
                },
                {
                    "entity_id": "device_tracker.andys_iphone",
                    "state": "home",
                    "attributes": {"friendly_name": "Andy’s iPhone"},
                },
                {
                    "entity_id": "device_tracker.2023_lexus_current_location",
                    "state": "not_home",
                    "attributes": {"friendly_name": "2023 Lexus Current Location"},
                },
            ],
        )

    integration = HomeAssistantIntegration(
        "http://ha.test",
        "ha-secret",
        2,
        transport=httpx.MockTransport(handler),
    )
    snapshot = await integration.snapshot()
    assert snapshot.metrics["people_home"] == 1
    assert snapshot.metrics["people_total"] == 1
    assert snapshot.metrics["presence"] == [
        {
            "entity_id": "device_tracker.andys_iphone",
            "name": "Andy’s iPhone",
            "state": "home",
            "unit": "",
        }
    ]


@pytest.mark.asyncio
async def test_home_assistant_explicit_unknown_presence_is_hidden() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "entity_id": "device_tracker.andys_iphone",
                    "state": "unknown",
                    "attributes": {"friendly_name": "Andy’s iPhone"},
                }
            ],
        )

    integration = HomeAssistantIntegration(
        "http://ha.test",
        "ha-secret",
        2,
        presence_entities="device_tracker.andys_iphone",
        transport=httpx.MockTransport(handler),
    )
    snapshot = await integration.snapshot()
    assert snapshot.status == "online"
    assert snapshot.metrics["people_total"] == 0
    assert snapshot.metrics["presence"] == []


@pytest.mark.asyncio
async def test_home_assistant_adapter_marks_missing_configured_entity_degraded() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    integration = HomeAssistantIntegration(
        "http://ha.test",
        "ha-secret",
        2,
        temperature_entities="sensor.missing_temperature",
        transport=httpx.MockTransport(handler),
    )
    snapshot = await integration.snapshot()
    assert snapshot.healthy is True
    assert snapshot.status == "degraded"
    assert snapshot.metrics["missing_entities"] == ["sensor.missing_temperature"]
