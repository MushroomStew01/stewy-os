import json
from datetime import UTC, datetime

import httpx
import pytest

from app.config import Settings
from app.models import ActivityEvent
from app.services.notifications import NotificationService, event_severity, is_quiet_time


def test_event_severity_prioritizes_critical_warning_and_info() -> None:
    assert event_severity("movie_change") == "critical"
    assert event_severity("container_stopped") == "critical"
    assert event_severity("github_action_failed") == "warning"
    assert event_severity("presence_arrived") == "info"


def test_quiet_hours_cross_midnight() -> None:
    late = datetime(2026, 8, 16, 4, 0, tzinfo=UTC)
    daytime = datetime(2026, 8, 16, 16, 0, tzinfo=UTC)
    assert is_quiet_time(late, "23:00", "07:00", "America/Toronto") is True
    assert is_quiet_time(daytime, "23:00", "07:00", "America/Toronto") is False


@pytest.mark.asyncio
async def test_discord_payload_mentions_user_for_warning() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(204)

    settings = Settings(
        _env_file=None,
        notifications_enabled=True,
        discord_webhook_url="https://discord.test/webhook",
        discord_user_id="1234567890",
    )
    service = NotificationService(settings, transport=httpx.MockTransport(handler))
    event = ActivityEvent(
        id=1,
        source="github",
        event_type="github_action_failed",
        title="stewy-os Actions failed",
        detail="Latest CI run is failing.",
        occurred_at=datetime(2026, 8, 16, 0, 0, tzinfo=UTC),
    )

    await service._send_discord(event, "warning")

    assert captured["content"] == "<@1234567890>"
    embeds = captured["embeds"]
    assert isinstance(embeds, list)
    assert embeds[0]["title"] == "stewy-os Actions failed"
