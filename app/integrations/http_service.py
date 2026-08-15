from __future__ import annotations

from typing import Any

import httpx

from .base import Integration, IntegrationSnapshot


class HTTPIntegration(Integration):
    def __init__(
        self,
        base_url: str,
        timeout: float,
        *,
        headers: dict[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = headers or {}
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    async def _get_json(self, path: str, *, headers: dict[str, str] | None = None) -> Any:
        request_headers = dict(self.headers)
        if headers:
            request_headers.update(headers)
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=request_headers,
            transport=self.transport,
            follow_redirects=True,
        ) as client:
            response = await client.get(path)
            response.raise_for_status()
            return response.json()

    def unavailable(self, detail: str) -> IntegrationSnapshot:
        return IntegrationSnapshot(
            name=self.name,
            label=self.label,
            configured=self.configured,
            healthy=False,
            status="not_configured" if not self.configured else "unavailable",
            detail=detail,
            link=self.base_url or None,
        )
