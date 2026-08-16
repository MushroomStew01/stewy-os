import httpx
import pytest

from app.integrations.docker import DockerIntegration
from app.integrations.github_status import GitHubIntegration


@pytest.mark.asyncio
async def test_github_adapter_maps_latest_action_runs() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Bearer token"
        if "/repos/MushroomStew01/stewy-os/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "workflow_runs": [
                        {
                            "name": "CI",
                            "status": "completed",
                            "conclusion": "success",
                            "event": "push",
                            "head_branch": "main",
                            "run_number": 12,
                            "updated_at": "2026-08-16T00:00:00Z",
                            "html_url": "https://github.com/example/success",
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "workflow_runs": [
                    {
                        "name": "CI",
                        "status": "completed",
                        "conclusion": "failure",
                        "event": "push",
                        "head_branch": "main",
                        "run_number": 8,
                        "updated_at": "2026-08-16T00:01:00Z",
                        "html_url": "https://github.com/example/failure",
                    }
                ]
            },
        )

    integration = GitHubIntegration(
        "MushroomStew01",
        "stewy-os,lexus-personal-hub",
        "token",
        2,
        600,
        transport=httpx.MockTransport(handler),
    )
    snapshot = await integration.snapshot()

    assert snapshot.healthy is True
    assert snapshot.status == "degraded"
    assert snapshot.metrics["repo_count"] == 2
    assert snapshot.metrics["success_count"] == 1
    assert snapshot.metrics["failing_count"] == 1
    assert snapshot.metrics["repos"][0]["name"] == "stewy-os"


@pytest.mark.asyncio
async def test_docker_adapter_maps_container_health() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/version":
            return httpx.Response(200, json={"Version": "28.3.3"})
        assert request.url.path == "/containers/json"
        return httpx.Response(
            200,
            json=[
                {
                    "Id": "a" * 64,
                    "Names": ["/stewy-os"],
                    "Image": "stewy-os-stewy-os",
                    "State": "running",
                    "Status": "Up 10 minutes (healthy)",
                },
                {
                    "Id": "b" * 64,
                    "Names": ["/broken-service"],
                    "Image": "broken:latest",
                    "State": "running",
                    "Status": "Up 2 minutes (unhealthy)",
                },
                {
                    "Id": "c" * 64,
                    "Names": ["/old-service"],
                    "Image": "old:latest",
                    "State": "exited",
                    "Status": "Exited (0) 2 days ago",
                },
            ],
        )

    integration = DockerIntegration(
        "/var/run/docker.sock",
        2,
        transport=httpx.MockTransport(handler),
    )
    snapshot = await integration.snapshot()

    assert snapshot.healthy is True
    assert snapshot.status == "degraded"
    assert snapshot.metrics["running_count"] == 2
    assert snapshot.metrics["unhealthy_count"] == 1
    assert snapshot.metrics["stopped_count"] == 1
    assert snapshot.metrics["engine_version"] == "28.3.3"
    assert snapshot.metrics["containers"][0]["name"] == "broken-service"


@pytest.mark.asyncio
async def test_docker_adapter_reports_unavailable_api() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    integration = DockerIntegration(
        "/var/run/docker.sock",
        2,
        transport=httpx.MockTransport(handler),
    )
    snapshot = await integration.snapshot()

    assert snapshot.healthy is False
    assert snapshot.status == "unavailable"
