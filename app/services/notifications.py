from __future__ import annotations

import hashlib
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy import func, or_, select

from ..config import Settings
from ..database import session_scope
from ..models import ActivityEvent, NotificationDelivery

_SEVERITY_RANK = {"info": 10, "warning": 20, "critical": 30}
_CRITICAL_EVENTS = {
    "integration_unavailable",
    "container_stopped",
    "container_unhealthy",
    "movie_change",
}
_WARNING_EVENTS = {
    "github_action_failed",
    "storage_warning",
    "vehicle_attention",
}
_SEVERITY_COLORS = {
    "info": 0x8FC8FF,
    "warning": 0xFFC66B,
    "critical": 0xFF7272,
}
_FINAL_STATUSES = {
    "sent",
    "filtered",
    "deduplicated",
    "suppressed_quiet_hours",
    "skipped_disabled",
    "skipped_not_configured",
}


def event_severity(event_type: str) -> str:
    if event_type in _CRITICAL_EVENTS:
        return "critical"
    if event_type in _WARNING_EVENTS:
        return "warning"
    return "info"


def _parse_clock(value: str, fallback: time) -> time:
    try:
        hour, minute = value.strip().split(":", 1)
        parsed = time(hour=int(hour), minute=int(minute))
    except (TypeError, ValueError):
        return fallback
    return parsed


def is_quiet_time(now: datetime, start: str, end: str, timezone: str) -> bool:
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        zone = UTC
    local_time = now.astimezone(zone).time().replace(tzinfo=None)
    start_time = _parse_clock(start, time(23, 0))
    end_time = _parse_clock(end, time(7, 0))
    if start_time == end_time:
        return False
    if start_time < end_time:
        return start_time <= local_time < end_time
    return local_time >= start_time or local_time < end_time


def _fingerprint(event: ActivityEvent) -> str:
    raw = "\x1f".join((event.source, event.event_type, event.title, event.detail))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class NotificationService:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.settings.discord_webhook_url.strip())

    def _minimum_rank(self) -> int:
        return _SEVERITY_RANK.get(self.settings.notification_min_severity.casefold(), 20)

    def _eligible_for_delivery(self, event: ActivityEvent, severity: str, now: datetime) -> str:
        if not self.settings.notifications_enabled:
            return "skipped_disabled"
        if not self.configured:
            return "skipped_not_configured"
        if _SEVERITY_RANK[severity] < self._minimum_rank():
            return "filtered"
        if severity != "critical" and is_quiet_time(
            now,
            self.settings.notification_quiet_start,
            self.settings.notification_quiet_end,
            self.settings.app_timezone,
        ):
            return "suppressed_quiet_hours"
        return "pending"

    def _was_recently_sent(self, fingerprint: str, now: datetime) -> bool:
        cutoff = now - timedelta(minutes=self.settings.notification_dedupe_minutes)
        with session_scope() as session:
            existing = session.scalar(
                select(NotificationDelivery.id)
                .where(NotificationDelivery.fingerprint == fingerprint)
                .where(NotificationDelivery.status == "sent")
                .where(NotificationDelivery.sent_at >= cutoff)
                .limit(1)
            )
        return existing is not None

    def _create_delivery(
        self,
        event: ActivityEvent,
        severity: str,
        fingerprint: str,
        status: str,
        now: datetime,
        reason: str = "",
    ) -> NotificationDelivery:
        with session_scope() as session:
            delivery = NotificationDelivery(
                event_id=event.id,
                channel="discord",
                severity=severity,
                status=status,
                reason=reason,
                attempts=0,
                fingerprint=fingerprint,
                created_at=now,
                updated_at=now,
            )
            session.add(delivery)
            session.flush()
            delivery_id = delivery.id
        with session_scope() as session:
            stored = session.get(NotificationDelivery, delivery_id)
            if stored is None:
                raise RuntimeError("Notification delivery disappeared after insert")
            session.expunge(stored)
            return stored

    def _pending_event_ids(self, now: datetime) -> list[int]:
        cutoff = now - timedelta(minutes=self.settings.notification_event_max_age_minutes)
        retry_cutoff = now - timedelta(minutes=self.settings.notification_retry_minutes)
        with session_scope() as session:
            fresh = list(
                session.scalars(
                    select(ActivityEvent.id)
                    .outerjoin(
                        NotificationDelivery,
                        NotificationDelivery.event_id == ActivityEvent.id,
                    )
                    .where(NotificationDelivery.id.is_(None))
                    .where(ActivityEvent.occurred_at >= cutoff)
                    .order_by(ActivityEvent.id.asc())
                    .limit(50)
                ).all()
            )
            retries = list(
                session.scalars(
                    select(NotificationDelivery.event_id)
                    .where(NotificationDelivery.status == "failed")
                    .where(NotificationDelivery.attempts < self.settings.notification_max_attempts)
                    .where(NotificationDelivery.updated_at <= retry_cutoff)
                    .order_by(NotificationDelivery.updated_at.asc())
                    .limit(20)
                ).all()
            )
        return list(dict.fromkeys([*fresh, *retries]))

    def _load_event_and_delivery(
        self,
        event_id: int,
    ) -> tuple[ActivityEvent | None, NotificationDelivery | None]:
        with session_scope() as session:
            event = session.get(ActivityEvent, event_id)
            delivery = session.scalar(
                select(NotificationDelivery).where(NotificationDelivery.event_id == event_id)
            )
            if event is not None:
                session.expunge(event)
            if delivery is not None:
                session.expunge(delivery)
            return event, delivery

    def _mark_delivery(
        self,
        delivery_id: int,
        *,
        status: str,
        attempts: int,
        now: datetime,
        reason: str = "",
        sent: bool = False,
    ) -> None:
        with session_scope() as session:
            delivery = session.get(NotificationDelivery, delivery_id)
            if delivery is None:
                return
            delivery.status = status
            delivery.attempts = attempts
            delivery.reason = reason[:1000]
            delivery.updated_at = now
            if sent:
                delivery.sent_at = now

    def _discord_payload(self, event: ActivityEvent, severity: str) -> dict[str, Any]:
        source_labels = {
            "movies": "Movies",
            "calories": "Nutrition",
            "lexus": "Lexus",
            "home_assistant": "Home",
            "system": "HomeLab",
            "github": "GitHub",
            "docker": "Docker",
        }
        occurred_at = event.occurred_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)
        payload: dict[str, Any] = {
            "username": self.settings.notification_discord_username,
            "allowed_mentions": {"parse": []},
            "embeds": [
                {
                    "title": event.title[:256],
                    "description": event.detail[:4096] or "Stewy OS detected a change.",
                    "color": _SEVERITY_COLORS[severity],
                    "fields": [
                        {
                            "name": "Source",
                            "value": source_labels.get(event.source, event.source.title()),
                            "inline": True,
                        },
                        {"name": "Priority", "value": severity.upper(), "inline": True},
                    ],
                    "footer": {"text": "Stewy OS v0.5"},
                    "timestamp": occurred_at.astimezone(UTC).isoformat(),
                }
            ],
        }
        user_id = self.settings.discord_user_id.strip()
        if user_id and severity in {"warning", "critical"}:
            payload["content"] = f"<@{user_id}>"
            payload["allowed_mentions"] = {"users": [user_id]}
        return payload

    async def _send_discord(self, event: ActivityEvent, severity: str) -> None:
        async with httpx.AsyncClient(
            timeout=self.settings.notification_timeout_seconds,
            transport=self.transport,
            follow_redirects=True,
        ) as client:
            response = await client.post(
                self.settings.discord_webhook_url,
                json=self._discord_payload(event, severity),
            )
            response.raise_for_status()

    async def _process_event(self, event_id: int, now: datetime) -> None:
        event, delivery = self._load_event_and_delivery(event_id)
        if event is None:
            return

        severity = event_severity(event.event_type)
        fingerprint = _fingerprint(event)

        if delivery is None:
            status = self._eligible_for_delivery(event, severity, now)
            if status == "pending" and self._was_recently_sent(fingerprint, now):
                status = "deduplicated"
            delivery = self._create_delivery(event, severity, fingerprint, status, now)
            if status in _FINAL_STATUSES:
                return
        elif delivery.status != "failed":
            return
        else:
            status = self._eligible_for_delivery(event, severity, now)
            if status != "pending":
                self._mark_delivery(
                    delivery.id,
                    status=status,
                    attempts=delivery.attempts,
                    now=now,
                )
                return

        attempts = delivery.attempts + 1
        try:
            await self._send_discord(event, severity)
        except httpx.HTTPError as exc:
            self._mark_delivery(
                delivery.id,
                status="failed",
                attempts=attempts,
                now=now,
                reason=f"{type(exc).__name__}: {exc}",
            )
            return
        self._mark_delivery(
            delivery.id,
            status="sent",
            attempts=attempts,
            now=now,
            sent=True,
        )

    async def process_pending(self) -> None:
        now = datetime.now(UTC)
        for event_id in self._pending_event_ids(now):
            await self._process_event(event_id, now)

    def summary(self) -> dict[str, Any]:
        with session_scope() as session:
            sent_count = int(
                session.scalar(
                    select(func.count(NotificationDelivery.id)).where(
                        NotificationDelivery.status == "sent"
                    )
                )
                or 0
            )
            failed_count = int(
                session.scalar(
                    select(func.count(NotificationDelivery.id)).where(
                        NotificationDelivery.status == "failed"
                    )
                )
                or 0
            )
            suppressed_count = int(
                session.scalar(
                    select(func.count(NotificationDelivery.id)).where(
                        or_(
                            NotificationDelivery.status == "suppressed_quiet_hours",
                            NotificationDelivery.status == "deduplicated",
                            NotificationDelivery.status == "filtered",
                        )
                    )
                )
                or 0
            )
            last = session.scalar(
                select(NotificationDelivery)
                .order_by(NotificationDelivery.updated_at.desc())
                .limit(1)
            )

        enabled = self.settings.notifications_enabled
        configured = self.configured
        if not enabled:
            status = "disabled"
        elif not configured:
            status = "not_configured"
        elif failed_count:
            status = "degraded"
        else:
            status = "online"

        return {
            "label": "Notifications",
            "enabled": enabled,
            "configured": configured,
            "status": status,
            "detail": "Discord notifications",
            "metrics": {
                "sent_count": sent_count,
                "failed_count": failed_count,
                "suppressed_count": suppressed_count,
                "min_severity": self.settings.notification_min_severity.casefold(),
                "quiet_hours": (
                    f"{self.settings.notification_quiet_start}–"
                    f"{self.settings.notification_quiet_end}"
                ),
                "last_status": last.status if last is not None else None,
                "last_sent_at": (
                    last.sent_at.isoformat() if last is not None and last.sent_at else None
                ),
            },
        }

    def recent_deliveries(self, limit: int = 20) -> list[dict[str, Any]]:
        with session_scope() as session:
            rows = session.execute(
                select(NotificationDelivery, ActivityEvent)
                .join(ActivityEvent, ActivityEvent.id == NotificationDelivery.event_id)
                .order_by(NotificationDelivery.updated_at.desc())
                .limit(limit)
            ).all()
        return [
            {
                "id": delivery.id,
                "event_id": event.id,
                "source": event.source,
                "event_type": event.event_type,
                "title": event.title,
                "severity": delivery.severity,
                "channel": delivery.channel,
                "status": delivery.status,
                "attempts": delivery.attempts,
                "reason": delivery.reason,
                "sent_at": delivery.sent_at.isoformat() if delivery.sent_at else None,
                "updated_at": delivery.updated_at.isoformat(),
            }
            for delivery, event in rows
        ]
