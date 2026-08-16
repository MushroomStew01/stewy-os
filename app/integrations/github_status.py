from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from .base import Integration, IntegrationSnapshot


def _split_repositories(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _repo_full_name(owner: str, value: str) -> str:
    return value if "/" in value else f"{owner}/{value}"


def _run_state(run: dict[str, Any]) -> str:
    status = str(run.get("status") or "").casefold()
    conclusion = str(run.get("conclusion") or "").casefold()
    if status and status != "completed":
        return "running"
    if conclusion == "success":
        return "success"
    if conclusion in {
        "failure",
        "cancelled",
        "timed_out",
        "action_required",
        "startup_failure",
        "stale",
    }:
        return "failure"
    if conclusion in {"neutral", "skipped"}:
        return "neutral"
    return "unknown"


class GitHubIntegration(Integration):
    name = "github"
    label = "GitHub"

    def __init__(
        self,
        owner: str,
        repositories: str,
        token: str,
        timeout: float,
        poll_seconds: int,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.owner = owner.strip()
        self.repositories = _split_repositories(repositories)
        self.token = token.strip()
        self.timeout = timeout
        self.poll_seconds = poll_seconds
        self.transport = transport
        self._cached: IntegrationSnapshot | None = None
        self._cached_at = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.owner and self.repositories)

    async def _fetch_repo(
        self,
        client: httpx.AsyncClient,
        repository: str,
    ) -> dict[str, Any]:
        full_name = _repo_full_name(self.owner, repository)
        try:
            response = await client.get(
                f"/repos/{full_name}/actions/runs",
                params={"per_page": 1},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return {
                "repo": full_name,
                "name": full_name.split("/", 1)[-1],
                "state": "error",
                "workflow": None,
                "event": None,
                "branch": None,
                "run_number": None,
                "updated_at": None,
                "url": f"https://github.com/{full_name}/actions",
                "error": type(exc).__name__,
            }

        runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
        if not isinstance(runs, list) or not runs:
            return {
                "repo": full_name,
                "name": full_name.split("/", 1)[-1],
                "state": "no_runs",
                "workflow": None,
                "event": None,
                "branch": None,
                "run_number": None,
                "updated_at": None,
                "url": f"https://github.com/{full_name}/actions",
                "error": None,
            }

        run = runs[0] if isinstance(runs[0], dict) else {}
        return {
            "repo": full_name,
            "name": full_name.split("/", 1)[-1],
            "state": _run_state(run),
            "workflow": run.get("name"),
            "event": run.get("event"),
            "branch": run.get("head_branch"),
            "run_number": run.get("run_number"),
            "updated_at": run.get("updated_at"),
            "url": run.get("html_url") or f"https://github.com/{full_name}/actions",
            "error": None,
        }

    async def _refresh(self) -> IntegrationSnapshot:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Stewy-OS",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=headers,
            timeout=self.timeout,
            transport=self.transport,
            follow_redirects=True,
        ) as client:
            repos = await asyncio.gather(
                *(self._fetch_repo(client, repository) for repository in self.repositories)
            )

        success = sum(1 for repo in repos if repo["state"] == "success")
        failing = sum(1 for repo in repos if repo["state"] == "failure")
        running = sum(1 for repo in repos if repo["state"] == "running")
        errors = sum(1 for repo in repos if repo["state"] == "error")
        no_runs = sum(
            1
            for repo in repos
            if repo["state"] in {"no_runs", "unknown", "neutral"}
        )
        healthy = errors < len(repos)
        status = "online"
        if not healthy:
            status = "unavailable"
        elif failing or errors:
            status = "degraded"

        observed_values = [
            str(repo["updated_at"])
            for repo in repos
            if repo.get("updated_at")
        ]
        detail = f"{len(repos)} repos • {success} green"
        if failing:
            detail += f" • {failing} failing"
        if errors:
            detail += f" • {errors} unavailable"

        return IntegrationSnapshot(
            name=self.name,
            label=self.label,
            configured=True,
            healthy=healthy,
            status=status,
            metrics={
                "repo_count": len(repos),
                "success_count": success,
                "failing_count": failing,
                "running_count": running,
                "other_count": no_runs,
                "error_count": errors,
                "repos": repos,
                "poll_seconds": self.poll_seconds,
                "authenticated": bool(self.token),
            },
            detail=detail,
            link=f"https://github.com/{self.owner}",
            observed_at=max(observed_values, default=None),
        )

    async def snapshot(self) -> IntegrationSnapshot:
        if not self.configured:
            return IntegrationSnapshot(
                name=self.name,
                label=self.label,
                configured=False,
                healthy=False,
                status="not_configured",
                detail="Set GITHUB_OWNER and GITHUB_REPOSITORIES.",
            )

        now = time.monotonic()
        if self._cached is not None and now - self._cached_at < self.poll_seconds:
            return self._cached

        try:
            snapshot = await self._refresh()
        except (httpx.HTTPError, ValueError) as exc:
            snapshot = IntegrationSnapshot(
                name=self.name,
                label=self.label,
                configured=True,
                healthy=False,
                status="unavailable",
                detail=f"GitHub request failed: {type(exc).__name__}",
                link=f"https://github.com/{self.owner}",
            )
        self._cached = snapshot
        self._cached_at = now
        return snapshot
