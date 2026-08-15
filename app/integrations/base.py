from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class IntegrationSnapshot:
    name: str
    label: str
    configured: bool
    healthy: bool
    status: str
    metrics: dict[str, Any] = field(default_factory=dict)
    detail: str = ""
    link: str | None = None
    observed_at: str | None = None
    fetched_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "configured": self.configured,
            "healthy": self.healthy,
            "status": self.status,
            "metrics": self.metrics,
            "detail": self.detail,
            "link": self.link,
            "observed_at": self.observed_at,
            "fetched_at": self.fetched_at,
        }


class Integration(ABC):
    name: str
    label: str

    @abstractmethod
    async def snapshot(self) -> IntegrationSnapshot:
        raise NotImplementedError
