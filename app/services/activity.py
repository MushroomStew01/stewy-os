from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from ..database import session_scope
from ..integrations.base import IntegrationSnapshot
from ..models import ActivityEvent, IntegrationState

_TRACKED_SOURCES = {"lexus", "calories", "movies", "system"}


def _list_metric(metrics: dict[str, Any], key: str) -> list[str]:
    value = metrics.get(key)
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _snapshot_state(snapshot: IntegrationSnapshot) -> dict[str, Any]:
    metrics = snapshot.metrics
    common = {
        "healthy": snapshot.healthy,
        "status": snapshot.status,
    }
    if snapshot.name == "calories":
        common["metrics"] = {
            "meal_count": metrics.get("meal_count"),
            "calories": metrics.get("calories"),
            "calorie_goal": metrics.get("calorie_goal"),
        }
    elif snapshot.name == "movies":
        common["metrics"] = {
            "title": metrics.get("title"),
            "ticket_available": metrics.get("ticket_available"),
            "theatres": _list_metric(metrics, "theatres"),
            "showtimes": _list_metric(metrics, "showtimes"),
            "dates": _list_metric(metrics, "dates"),
            "formats": _list_metric(metrics, "formats"),
            "state_id": metrics.get("state_id"),
        }
    elif snapshot.name == "lexus":
        common["metrics"] = {"ready": metrics.get("ready")}
    else:
        common["metrics"] = {}
    return common


def _health_events(
    source: str, previous: dict[str, Any], current: dict[str, Any]
) -> list[tuple[str, str, str]]:
    old = bool(previous.get("healthy"))
    new = bool(current.get("healthy"))
    if old == new:
        return []
    labels = {
        "lexus": "Lexus",
        "calories": "Nutrition",
        "movies": "Movie Monitor",
        "system": "HomeLab",
    }
    label = labels.get(source, source.title())
    if new:
        return [
            ("integration_recovered", f"{label} recovered", "The integration is responding again.")
        ]
    return [
        (
            "integration_unavailable",
            f"{label} unavailable",
            "The integration is not currently healthy.",
        )
    ]


def _calorie_events(
    previous: dict[str, Any], current: dict[str, Any]
) -> list[tuple[str, str, str]]:
    old_metrics = previous.get("metrics", {})
    new_metrics = current.get("metrics", {})
    old_meals = int(old_metrics.get("meal_count") or 0)
    new_meals = int(new_metrics.get("meal_count") or 0)
    if new_meals <= old_meals:
        return []
    delta = new_meals - old_meals
    calories = new_metrics.get("calories")
    goal = new_metrics.get("calorie_goal")
    detail = f"{delta} new meal{'s' if delta != 1 else ''} logged"
    if calories is not None and goal is not None:
        detail += f" • {calories:g} / {goal:g} kcal today"
    return [("meal_logged", "Meal logged", detail)]


def _movie_events(previous: dict[str, Any], current: dict[str, Any]) -> list[tuple[str, str, str]]:
    old = previous.get("metrics", {})
    new = current.get("metrics", {})
    title = str(new.get("title") or "Movie")
    parts: list[str] = []

    old_ticket = bool(old.get("ticket_available"))
    new_ticket = bool(new.get("ticket_available"))
    if old_ticket != new_ticket:
        parts.append("Tickets detected" if new_ticket else "Ticket availability disappeared")

    old_theatres = set(_list_metric(old, "theatres"))
    new_theatres = set(_list_metric(new, "theatres"))
    added_theatres = sorted(new_theatres - old_theatres)
    if added_theatres:
        parts.append(f"New theatre: {', '.join(added_theatres)}")

    old_times = set(_list_metric(old, "showtimes"))
    new_times = sorted(set(_list_metric(new, "showtimes")) - old_times)
    if new_times:
        parts.append(f"New showtimes: {', '.join(new_times[:8])}")

    old_dates = set(_list_metric(old, "dates"))
    new_dates = sorted(set(_list_metric(new, "dates")) - old_dates)
    if new_dates:
        parts.append(f"New dates: {', '.join(new_dates[:6])}")

    old_formats = set(_list_metric(old, "formats"))
    new_formats = sorted(set(_list_metric(new, "formats")) - old_formats)
    if new_formats:
        parts.append(f"New formats: {', '.join(new_formats[:6])}")

    if not parts:
        return []
    if new_ticket and not old_ticket:
        heading = f"{title} tickets detected"
    elif new_times:
        heading = f"New {title} showtimes"
    elif added_theatres:
        heading = f"{title} reached a new theatre"
    else:
        heading = f"{title} availability changed"
    return [("movie_change", heading, " • ".join(parts))]


def _lexus_events(previous: dict[str, Any], current: dict[str, Any]) -> list[tuple[str, str, str]]:
    old_ready = previous.get("metrics", {}).get("ready")
    new_ready = current.get("metrics", {}).get("ready")
    if old_ready is None or new_ready is None or old_ready == new_ready:
        return []
    if bool(new_ready):
        return [("vehicle_ready", "Lexus back to ready", "Vehicle status returned to ready.")]
    return [("vehicle_attention", "Lexus needs attention", "Vehicle ready status changed to no.")]


def _events_for_transition(
    source: str,
    previous: dict[str, Any],
    current: dict[str, Any],
) -> list[tuple[str, str, str]]:
    events = _health_events(source, previous, current)
    if source == "calories":
        events.extend(_calorie_events(previous, current))
    elif source == "movies":
        events.extend(_movie_events(previous, current))
    elif source == "lexus":
        events.extend(_lexus_events(previous, current))
    return events


def reconcile_activity(snapshots: list[IntegrationSnapshot]) -> None:
    now = datetime.now(UTC)
    with session_scope() as session:
        for snapshot in snapshots:
            if snapshot.name not in _TRACKED_SOURCES:
                continue
            current = _snapshot_state(snapshot)
            serialized = json.dumps(current, sort_keys=True, separators=(",", ":"))
            stored = session.get(IntegrationState, snapshot.name)
            if stored is None:
                session.add(
                    IntegrationState(source=snapshot.name, payload=serialized, updated_at=now)
                )
                continue
            if stored.payload == serialized:
                continue
            try:
                previous = json.loads(stored.payload)
            except json.JSONDecodeError:
                previous = {}
            for event_type, title, detail in _events_for_transition(
                snapshot.name, previous, current
            ):
                session.add(
                    ActivityEvent(
                        source=snapshot.name,
                        event_type=event_type,
                        title=title,
                        detail=detail,
                        occurred_at=now,
                    )
                )
            stored.payload = serialized
            stored.updated_at = now


def recent_activity(limit: int = 20) -> list[dict[str, object]]:
    with session_scope() as session:
        events = list(
            session.scalars(
                select(ActivityEvent).order_by(ActivityEvent.occurred_at.desc()).limit(limit)
            ).all()
        )
    return [
        {
            "id": event.id,
            "source": event.source,
            "event_type": event.event_type,
            "title": event.title,
            "detail": event.detail,
            "occurred_at": event.occurred_at.isoformat(),
        }
        for event in events
    ]
