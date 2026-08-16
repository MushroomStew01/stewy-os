# Stewy OS

Stewy OS is a self-hosted personal command center that sits above independent
services instead of merging their business logic and databases into one monolith.

## v0.4

v0.4 adds the Developer / HomeLab layer.

- Lexus Personal Hub status via `/healthz` and `/api/status`.
- ChatGPT Calorie Bridge daily summary via `/health` and `/api/summary`.
- Movie Ticket Monitor status through its public `status.json` feed.
- Home Assistant service health, presence, room temperatures, and selected entities.
- Raspberry Pi CPU, RAM, disk, temperature, load, and human-readable uptime.
- GitHub Actions status for the core Stewy repositories.
- Docker Engine/container status, including running, stopped, and unhealthy containers.
- Persistent Recent Activity for meals, movies, presence, GitHub failures/recovery,
  Docker transitions, integration health, Lexus ready state, and storage warnings.
- Docker named-volume persistence and responsive PWA dashboard on port `8020`.

## Architecture

```text
                         +--------------------+
                         |      Stewy OS      |
                         |  FastAPI + PWA UI  |
                         +----------+---------+
                                    |
       +---------------+------------+-------------+---------------+
       |               |                          |               |
       v               v                          v               v
   Lexus Hub      Calorie Bridge             Movie Monitor   Home Assistant
  /api/status      /api/summary               status.json      /api/states
       |
       +-----------------------+
                               |
                               v
                        Raspberry Pi host
                       psutil + Docker API
                               |
                               v
                         GitHub REST API
                        Actions run status
```

Stewy OS owns presentation, integration health, short-lived caching, and the
normalized activity timeline. Source services continue to own their data and
domain logic.

## Raspberry Pi / Docker

```bash
cp .env.example .env
nano .env
docker compose up -d --build
```

Stewy OS is exposed on:

```text
http://<PI-IP>:8020
```

The Compose deployment uses the `stewy_data` named volume for SQLite.

### Docker status access

v0.4 mounts `/var/run/docker.sock` into Stewy OS so it can read Docker Engine
status. The application only issues `GET` requests, but access to a Docker socket
is inherently privileged. Keep Stewy OS on trusted LAN/Tailscale networks and keep
dashboard authentication enabled before exposing it beyond those networks.

The Stewy OS container runs as a non-root user. Set the host Docker socket group
ID in `.env`:

```bash
stat -c '%g' /var/run/docker.sock
```

Then set:

```env
DOCKER_GID=988
```

using the number returned by the command.

## Configuration

### Lexus Personal Hub

When Lexus Hub runs directly on the same Raspberry Pi while Stewy OS runs in
Docker:

```env
LEXUS_BASE_URL=http://host.docker.internal:8000
LEXUS_TIMEOUT_SECONDS=5
```

### Calorie Bridge

```env
CALORIE_BASE_URL=https://your-calorie-service.example
CALORIE_API_KEY=replace-with-your-existing-app-api-key
CALORIE_TIMEOUT_SECONDS=5
```

### Movie Monitor

```env
MOVIE_STATUS_URL=https://raw.githubusercontent.com/MushroomStew01/movie-ticket-discord-monitor/main/status.json
MOVIE_TIMEOUT_SECONDS=5
MOVIE_STALE_HOURS=36
```

### Home Assistant

```env
HA_BASE_URL=http://host.docker.internal:8123
HA_TOKEN=replace-with-your-long-lived-home-assistant-token
HA_TIMEOUT_SECONDS=5

HA_PRESENCE_ENTITIES=
HA_TEMPERATURE_ENTITIES=
HA_SELECTED_ENTITIES=
HA_MAX_TEMPERATURE_SENSORS=6
```

If `HA_PRESENCE_ENTITIES` is blank, Stewy OS first uses usable `person.*`
entities. If none exist it falls back to non-vehicle `device_tracker.*` entities.
Lexus/Toyota trackers and `unknown` / `unavailable` presence are hidden.

### GitHub

The four core public repositories are monitored by default:

```env
GITHUB_OWNER=MushroomStew01
GITHUB_REPOSITORIES=stewy-os,lexus-personal-hub,chatgpt-calorie-bridge,movie-ticket-discord-monitor
GITHUB_TOKEN=
GITHUB_TIMEOUT_SECONDS=5
GITHUB_POLL_SECONDS=600
```

A token is optional for public repositories. Without one, Stewy OS intentionally
caches GitHub status for 10 minutes. Four repositories at that interval use about
24 unauthenticated API requests per hour, below GitHub's standard unauthenticated
REST rate limit. Set `GITHUB_TOKEN` to a fine-grained read-only token if you later
add private repositories or want more headroom.

The GitHub card shows each repository's latest Actions run and creates activity
events when a repository changes into a failing state or recovers to green.

### Docker

```env
DOCKER_SOCKET_PATH=/var/run/docker.sock
DOCKER_TIMEOUT_SECONDS=3
DOCKER_GID=988
```

`DOCKER_GID` is consumed by Docker Compose. `DOCKER_SOCKET_PATH` is consumed by
Stewy OS itself.

### Dashboard protection

For LAN/Tailscale testing, `STEWY_PASSWORD` may remain blank. Before exposing the
service more broadly, set a strong password:

```env
STEWY_USERNAME=andy
STEWY_PASSWORD=replace-with-a-long-random-secret
```

## API

- `GET /healthz` — Stewy OS process health and version.
- `GET /api/dashboard` — combined integration snapshot and recent activity.
- `GET /api/dashboard?force=true` — bypass the short dashboard cache.
- `GET /api/activity` — persistent normalized activity events.

The GitHub integration maintains its own longer poll cache, so `force=true` does
not burn GitHub API quota.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest -q
```

## Roadmap

### v0.5 — Notifications

- One notification service across Lexus, movies, HomeLab, GitHub, and future sources.
- Deduplication, priorities, quiet hours, and Discord delivery.

### v0.6 — Personal intelligence

- Daily briefing.
- Cross-service questions and summaries.
- Ask Stewy interface.
