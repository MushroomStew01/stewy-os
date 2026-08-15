# Stewy OS

Stewy OS is a self-hosted personal command center that sits above independent
services instead of merging their business logic and databases into one monolith.

## v0.3

v0.3 connects Home Assistant directly to the command center while keeping the
integration read-only.

- Lexus Personal Hub status via `/healthz` and `/api/status`.
- ChatGPT Calorie Bridge daily summary via `/health` and `/api/summary`.
- Movie Ticket Monitor status through its public `status.json` feed.
- Home Assistant service health, presence, room temperatures, and explicitly selected entities.
- Automatic `person.*` presence discovery and sensible temperature-sensor discovery when entity lists are blank.
- Presence-change activity events such as arrivals and departures.
- Raspberry Pi / HomeLab CPU, RAM, disk, temperature, load, and uptime.
- Persistent Recent Activity with SQLite-backed integration cursors.
- Docker named-volume persistence and responsive PWA dashboard on port `8020`.

## Architecture

```text
                         +--------------------+
                         |      Stewy OS      |
                         |  FastAPI + PWA UI  |
                         +----------+---------+
                                    |
        +----------------+----------------+----------------+----------------+
        |                |                |                |
        v                v                v                v
   Lexus Hub        Calorie Bridge    Movie Monitor   Home Assistant
  /api/status        /api/summary      status.json      /api/states
        |                                 |                |
        v                                 v                v
 Home Assistant                      GitHub Actions   Home / sensors
                                    |
                                    v
                              HomeLab / Pi
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

The Compose deployment uses a Docker named volume named `stewy_data`. This lets
the non-root application user write SQLite safely without a host-side `chown`.

If you are upgrading from v0.1, the old `./data/stewy.db` bind-mounted database
is no longer used after the first v0.2 Compose deployment. v0.1 only stored the
empty/new activity foundation, so the v0.2 named volume intentionally starts the
activity cursor cleanly.

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

The public movie-monitor status feed is configured by default:

```env
MOVIE_STATUS_URL=https://raw.githubusercontent.com/MushroomStew01/movie-ticket-discord-monitor/main/status.json
MOVIE_TIMEOUT_SECONDS=5
MOVIE_STALE_HOURS=36
```

A feed older than `MOVIE_STALE_HOURS` is shown as stale so Stewy OS can also
surface a stopped movie-monitor workflow.

### Home Assistant

Stewy OS uses the same Home Assistant REST pattern as Lexus Hub: a local base URL,
a long-lived access token, Bearer authentication, and `GET /api/states`. The
integration is read-only.

When Home Assistant is exposed on port `8123` of the same Raspberry Pi host:

```env
HA_BASE_URL=http://host.docker.internal:8123
HA_TOKEN=replace-with-your-long-lived-home-assistant-token
HA_TIMEOUT_SECONDS=5
```

Optional comma-separated entity lists let you keep the dashboard focused:

```env
HA_PRESENCE_ENTITIES=person.andy
HA_TEMPERATURE_ENTITIES=sensor.living_room_temperature,sensor.bedroom_temperature
HA_SELECTED_ENTITIES=binary_sensor.front_door,sensor.indoor_humidity
HA_MAX_TEMPERATURE_SENSORS=6
```

If `HA_PRESENCE_ENTITIES` is blank, Stewy OS discovers `person.*` entities. If
`HA_TEMPERATURE_ENTITIES` is blank, it discovers suitable Home Assistant sensors
with `device_class=temperature` and shows up to `HA_MAX_TEMPERATURE_SENSORS`.
Configured entity IDs that disappear are surfaced as a degraded Home card without
marking the Home Assistant API itself offline.

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
- `GET /api/dashboard?force=true` — bypass integration cache.
- `GET /api/activity` — persistent normalized activity events.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest -q
```

## Roadmap

### v0.4 — Developer / HomeLab

- Docker service status.
- GitHub repository and Actions status.
- Uptime checks and storage trends.

### v0.5 — Notifications

- One notification service across Lexus, movies, HomeLab, and future sources.
- Deduplication, priorities, quiet hours, and Discord delivery.

### v0.6 — Personal intelligence

- Daily briefing.
- Cross-service questions and summaries.
- Ask Stewy interface.
