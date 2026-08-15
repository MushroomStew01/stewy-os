from __future__ import annotations

import asyncio
import time
from typing import Any

from ..config import Settings
from ..integrations import CalorieIntegration, LexusIntegration, MovieIntegration, SystemIntegration
from ..integrations.base import Integration, IntegrationSnapshot
from .activity import recent_activity, reconcile_activity


class DashboardService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.integrations: list[Integration] = [
            LexusIntegration(settings.lexus_base_url, settings.lexus_timeout_seconds),
            CalorieIntegration(
                settings.calorie_base_url,
                settings.calorie_api_key,
                settings.calorie_timeout_seconds,
            ),
            MovieIntegration(
                settings.movie_status_url,
                settings.movie_timeout_seconds,
                settings.movie_stale_hours,
            ),
            SystemIntegration(),
        ]
        self._cache: dict[str, Any] | None = None
        self._cache_at = 0.0
        self._lock = asyncio.Lock()

    async def _fetch_integrations(self) -> list[IntegrationSnapshot]:
        results = await asyncio.gather(
            *(integration.snapshot() for integration in self.integrations),
            return_exceptions=True,
        )
        snapshots: list[IntegrationSnapshot] = []
        for integration, result in zip(self.integrations, results, strict=True):
            if isinstance(result, BaseException):
                snapshots.append(
                    IntegrationSnapshot(
                        name=integration.name,
                        label=integration.label,
                        configured=True,
                        healthy=False,
                        status="error",
                        detail=f"Unexpected integration error: {type(result).__name__}",
                    )
                )
            else:
                snapshots.append(result)
        return snapshots

    async def get_dashboard(self, *, force: bool = False) -> dict[str, Any]:
        ttl = self.settings.integration_cache_seconds
        if not force and self._cache is not None and time.monotonic() - self._cache_at < ttl:
            return self._cache

        async with self._lock:
            if not force and self._cache is not None and time.monotonic() - self._cache_at < ttl:
                return self._cache

            snapshots = await self._fetch_integrations()
            reconcile_activity(snapshots)
            payload = {
                "app": self.settings.app_name,
                "refresh_seconds": self.settings.app_refresh_seconds,
                "integrations": {snapshot.name: snapshot.as_dict() for snapshot in snapshots},
                "activity": recent_activity(limit=12),
            }
            self._cache = payload
            self._cache_at = time.monotonic()
            return payload
