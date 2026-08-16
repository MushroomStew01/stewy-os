from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from .base import Integration, IntegrationSnapshot


def _container_record(container: dict[str, Any]) -> dict[str, Any]:
    names = container.get("Names")
    if isinstance(names, list) and names:
        name = str(names[0]).lstrip("/")
    else:
        name = str(container.get("Id") or "")[:12] or "container"

    state = str(container.get("State") or "unknown").casefold()
    status_text = str(container.get("Status") or "")
    status_lower = status_text.casefold()
    health = None
    if "(unhealthy)" in status_lower:
        health = "unhealthy"
    elif "(healthy)" in status_lower:
        health = "healthy"

    return {
        "name": name,
        "image": str(container.get("Image") or ""),
        "state": state,
        "health": health,
        "status": status_text,
    }


class DockerIntegration(Integration):
    name = "docker"
    label = "Docker"

    def __init__(
        self,
        socket_path: str,
        timeout: float,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.socket_path = socket_path.strip()
        self.timeout = timeout
        self.transport = transport

    @property
    def configured(self) -> bool:
        if self.transport is not None:
            return True
        return bool(self.socket_path and Path(self.socket_path).exists())

    async def snapshot(self) -> IntegrationSnapshot:
        if not self.configured:
            return IntegrationSnapshot(
                name=self.name,
                label=self.label,
                configured=False,
                healthy=False,
                status="not_configured",
                detail="Docker socket is not available to Stewy OS.",
            )

        transport = self.transport
        if transport is None:
            transport = httpx.AsyncHTTPTransport(uds=self.socket_path)

        try:
            async with httpx.AsyncClient(
                base_url="http://docker",
                transport=transport,
                timeout=self.timeout,
            ) as client:
                version_response = await client.get("/version")
                version_response.raise_for_status()
                containers_response = await client.get(
                    "/containers/json",
                    params={"all": 1},
                )
                containers_response.raise_for_status()
                version_payload = version_response.json()
                container_payload = containers_response.json()
        except (httpx.HTTPError, OSError, ValueError) as exc:
            return IntegrationSnapshot(
                name=self.name,
                label=self.label,
                configured=True,
                healthy=False,
                status="unavailable",
                detail=f"Docker request failed: {type(exc).__name__}",
            )

        raw_containers = container_payload if isinstance(container_payload, list) else []
        containers = [
            _container_record(item)
            for item in raw_containers
            if isinstance(item, dict)
        ]
        containers.sort(
            key=lambda item: (
                item["health"] != "unhealthy",
                item["state"] != "running",
                str(item["name"]).casefold(),
            )
        )

        running = sum(1 for item in containers if item["state"] == "running")
        stopped = len(containers) - running
        unhealthy = sum(1 for item in containers if item["health"] == "unhealthy")
        engine_version = ""
        if isinstance(version_payload, dict):
            engine_version = str(version_payload.get("Version") or "")

        return IntegrationSnapshot(
            name=self.name,
            label=self.label,
            configured=True,
            healthy=True,
            status="degraded" if unhealthy else "online",
            metrics={
                "running_count": running,
                "stopped_count": stopped,
                "unhealthy_count": unhealthy,
                "container_count": len(containers),
                "engine_version": engine_version,
                "containers": containers,
            },
            detail=f"{running} running • Docker {engine_version or 'Engine'}",
        )
