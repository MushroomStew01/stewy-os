from __future__ import annotations

import httpx

from .base import IntegrationSnapshot
from .http_service import HTTPIntegration


class LexusIntegration(HTTPIntegration):
    name = "lexus"
    label = "Lexus"

    async def snapshot(self) -> IntegrationSnapshot:
        if not self.configured:
            return self.unavailable("Set LEXUS_BASE_URL to connect Lexus Personal Hub.")

        try:
            health = await self._get_json("/healthz")
            status = await self._get_json("/api/status")
        except (httpx.HTTPError, ValueError) as exc:
            return self.unavailable(f"Lexus Hub request failed: {type(exc).__name__}")

        healthy = isinstance(health, dict) and health.get("status") == "ok"
        return IntegrationSnapshot(
            name=self.name,
            label=self.label,
            configured=True,
            healthy=healthy,
            status="online" if healthy else "degraded",
            metrics={
                "ready": bool(status.get("ready")),
                "fuel_percent": status.get("fuel_percent"),
                "range_km": status.get("range_km"),
                "odometer_km": status.get("odometer_km"),
            },
            detail=str(status.get("vehicle") or status.get("display_name") or "Vehicle connected"),
            link=self.base_url,
            observed_at=str(status.get("observed_at")) if status.get("observed_at") else None,
        )
