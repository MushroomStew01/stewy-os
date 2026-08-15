# Stewy OS

Stewy OS is a self-hosted personal command center that sits above Andy's existing services instead of merging them into one monolith.

## v0.1 foundation

The first milestone includes:

- FastAPI web application and JSON dashboard API.
- Responsive dark dashboard and installable PWA shell.
- Live Raspberry Pi / host metrics for CPU, RAM, disk, temperature, load, and uptime.
- Lexus Personal Hub adapter using its existing `/healthz` and `/api/status` endpoints.
- ChatGPT Calorie Bridge adapter using `/health` and API-key-protected `/api/summary`.
- Concurrent integration polling with a short cache to avoid hammering upstream services.
- SQLite-backed activity-event foundation for the unified timeline.
- Optional HTTP Basic protection for the dashboard and APIs.
- Docker / Compose deployment and GitHub Actions CI.
- Adapter and application tests.

The movie monitor remains independent and will join through a compact machine-readable status feed in v0.2.

## Architecture

```text
                         +--------------------+
                         |      Stewy OS      |
                         |  FastAPI + PWA UI  |
                         +----------+---------+
                                    |
                 +------------------+------------------+
                 |                  |                  |
                 v                  v                  v
          Lexus Personal Hub   Calorie Bridge      HomeLab Host
             /api/status        /api/summary       psutil / Linux
                 |
           Home Assistant
```

Stewy OS owns presentation, integration health, caching, and eventually unified activity/notifications. Each source service continues to own its own business logic and data.

## Quick start

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

On Windows, activate the virtual environment with `.venv\\Scripts\\activate`.

Open `http://127.0.0.1:8000`.

## Raspberry Pi / Docker

```bash
cp .env.example .env
docker compose up -d --build
```

If Lexus Personal Hub runs directly on the same Raspberry Pi while Stewy OS runs in Docker, point the integration at the host bridge rather than `127.0.0.1` inside the container:

```env
LEXUS_BASE_URL=http://host.docker.internal:YOUR_LEXUS_PORT
```

The Compose file adds the Linux `host-gateway` mapping needed for that hostname.

## Configuration

### Lexus Personal Hub

```env
LEXUS_BASE_URL=http://127.0.0.1:8010
LEXUS_TIMEOUT_SECONDS=5
```

Stewy OS checks:

- `GET /healthz`
- `GET /api/status`

If the URL is blank or the service is unavailable, Stewy OS stays online and shows that card as unconfigured/unavailable.

### Calorie Bridge

```env
CALORIE_BASE_URL=https://your-calorie-service.example
CALORIE_API_KEY=replace-with-your-existing-app-api-key
CALORIE_TIMEOUT_SECONDS=5
```

Stewy OS checks:

- `GET /health`
- `GET /api/summary` with `X-API-Key`

### Dashboard protection

For LAN-only testing you can leave `STEWY_PASSWORD` blank. Before exposing Stewy OS outside the private network, set a strong password:

```env
STEWY_USERNAME=andy
STEWY_PASSWORD=replace-with-a-long-random-secret
```

This protects `/`, `/api/dashboard`, and `/api/activity`. `/healthz` intentionally remains unauthenticated for uptime checks.

## API

- `GET /healthz` — Stewy OS process health.
- `GET /api/dashboard` — combined current integration snapshot.
- `GET /api/dashboard?force=true` — bypass the short integration cache.
- `GET /api/activity` — recent unified activity events.

## Persistence

Stewy OS uses SQLite by default:

```env
DATABASE_URL=sqlite:///./data/stewy.db
```

The v0.1 database contains the `activity_events` table. Integration-owned data such as Lexus trips and meal history remains in the source applications.

## Development

```bash
ruff check .
pytest -q
```

## Roadmap

### v0.2 — Activity + movies

- Movie Monitor `status.json` feed.
- Generate normalized activity events from source-service changes.
- Better timestamps and source links.

### v0.3 — Home Assistant

- Rooms, temperatures, presence, selected entities, and service health.

### v0.4 — Developer / HomeLab

- Docker service status.
- GitHub repository and Actions status.
- Uptime checks and storage trends.

### v0.5 — Notifications

- One notification service for Lexus, movies, HomeLab, and future integrations.
- Deduplication, priorities, quiet hours, and Discord delivery.

### v0.6 — Personal intelligence

- Daily briefing.
- Cross-service questions and summaries.
- "Ask Stewy" interface.
