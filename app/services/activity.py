from __future__ import annotations

from sqlalchemy import select

from ..database import session_scope
from ..models import ActivityEvent


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
