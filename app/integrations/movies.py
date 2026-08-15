from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from .base import Integration, IntegrationSnapshot


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class MovieIntegration(Integration):
    name = "movies"
    label = "Movies"

    def __init__(
        self,
        status_url: str,
        timeout: float,
        stale_hours: int,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.status_url = status_url.strip()
        self.timeout = timeout
        self.stale_hours = stale_hours
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.status_url)

    def unavailable(self, detail: str) -> IntegrationSnapshot:
        return IntegrationSnapshot(
            name=self.name,
            label=self.label,
            configured=self.configured,
            healthy=False,
            status="not_configured" if not self.configured else "unavailable",
            detail=detail,
            link=self.status_url or None,
        )

    async def snapshot(self) -> IntegrationSnapshot:
        if not self.configured:
            return self.unavailable("Set MOVIE_STATUS_URL to connect the movie monitor.")

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                transport=self.transport,
                follow_redirects=True,
            ) as client:
                response = await client.get(self.status_url)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return self.unavailable(f"Movie status request failed: {type(exc).__name__}")

        if not isinstance(data, dict):
            return self.unavailable("Movie status feed returned an invalid payload.")

        priority_titles = _as_list(data.get("priority_titles"))
        priority_map = data.get("priority") if isinstance(data.get("priority"), dict) else {}
        title = priority_titles[0] if priority_titles else next(iter(priority_map), "Dune: Part 3")
        priority = priority_map.get(title, {}) if isinstance(priority_map, dict) else {}
        if not isinstance(priority, dict):
            priority = {}

        updated_at = _parse_timestamp(data.get("updated_at"))
        stale = updated_at is None or (
            datetime.now(UTC) - updated_at
        ).total_seconds() > self.stale_hours * 3600
        feed_healthy = bool(data.get("healthy", False))
        healthy = feed_healthy and not stale
        if stale:
            status = "stale"
        elif feed_healthy:
            status = "online"
        else:
            status = "degraded"

        theatres = _as_list(priority.get("theatres"))
        showtimes = _as_list(priority.get("showtimes"))
        dates = _as_list(priority.get("dates"))
        formats = _as_list(priority.get("formats"))
        monitored_theatres = int(data.get("theatre_count") or 0)
        detail = title
        if stale:
            detail = f"{title} • status feed stale"
        elif not feed_healthy:
            detail = f"{title} • monitor degraded"

        return IntegrationSnapshot(
            name=self.name,
            label=self.label,
            configured=True,
            healthy=healthy,
            status=status,
            metrics={
                "title": title,
                "ticket_available": bool(priority.get("ticket_available", False)),
                "theatres_found": len(theatres),
                "monitored_theatres": monitored_theatres,
                "showtime_count": len(showtimes),
                "format_count": len(formats),
                "theatres": theatres,
                "showtimes": showtimes,
                "dates": dates,
                "formats": formats,
                "state_id": str(data.get("state_id") or ""),
                "failing_targets": _as_list(data.get("failing_targets")),
            },
            detail=detail,
            link=self.status_url,
            observed_at=updated_at.isoformat() if updated_at else None,
        )
