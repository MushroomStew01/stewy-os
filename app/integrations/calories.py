from __future__ import annotations

import httpx

from .base import IntegrationSnapshot
from .http_service import HTTPIntegration


class CalorieIntegration(HTTPIntegration):
    name = "calories"
    label = "Nutrition"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        headers = {"X-API-Key": api_key} if api_key else {}
        super().__init__(base_url, timeout, headers=headers, transport=transport)
        self.api_key = api_key

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    async def snapshot(self) -> IntegrationSnapshot:
        if not self.configured:
            return self.unavailable("Set CALORIE_BASE_URL and CALORIE_API_KEY to connect meals.")

        try:
            health = await self._get_json("/health")
            summary = await self._get_json("/api/summary")
        except (httpx.HTTPError, ValueError) as exc:
            return self.unavailable(f"Calorie Bridge request failed: {type(exc).__name__}")

        healthy = isinstance(health, dict) and health.get("status") == "ok"
        goal = summary.get("calorie_goal")
        calories = summary.get("calories")
        progress = None
        if isinstance(goal, (int, float)) and goal > 0 and isinstance(calories, (int, float)):
            progress = round((float(calories) / float(goal)) * 100, 1)

        return IntegrationSnapshot(
            name=self.name,
            label=self.label,
            configured=True,
            healthy=healthy,
            status="online" if healthy else "degraded",
            metrics={
                "calories": calories,
                "calorie_goal": goal,
                "calories_remaining": summary.get("calories_remaining"),
                "protein_g": summary.get("protein"),
                "carbs_g": summary.get("carbs"),
                "fat_g": summary.get("fat"),
                "meal_count": summary.get("meal_count"),
                "progress_percent": progress,
            },
            detail=f"{summary.get('meal_count', 0)} meals today",
            link=self.base_url,
            observed_at=str(summary.get("date")) if summary.get("date") else None,
        )
