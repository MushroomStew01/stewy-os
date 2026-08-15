from __future__ import annotations

from typing import Any

import httpx

from .base import Integration, IntegrationSnapshot

_IGNORED_TEMPERATURE_TERMS = (
    "battery",
    "cpu",
    "processor",
    "gpu",
    "phone",
    "tablet",
    "lexus",
    "toyota",
    "vehicle",
    "tire",
    "fridge",
    "refrigerator",
    "freezer",
    "oven",
)

_IGNORED_PRESENCE_TERMS = (
    "lexus",
    "toyota",
    "vehicle",
    "current location",
    "current_location",
    "parked location",
    "parked_location",
)

_VALID_PRESENCE_STATES = {"home", "not_home"}


def _split_entities(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _attrs(state: dict[str, Any]) -> dict[str, Any]:
    attrs = state.get("attributes")
    return attrs if isinstance(attrs, dict) else {}


def _friendly_name(state: dict[str, Any]) -> str:
    return str(_attrs(state).get("friendly_name") or state.get("entity_id") or "Entity")


def _number(state: dict[str, Any]) -> float | None:
    raw = state.get("state")
    if raw in {None, "", "unknown", "unavailable"}:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _unit(state: dict[str, Any]) -> str:
    return str(_attrs(state).get("unit_of_measurement") or "").strip()


def _generic_record(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_id": str(state.get("entity_id") or ""),
        "name": _friendly_name(state),
        "state": str(state.get("state") or ""),
        "unit": _unit(state),
    }


def _temperature_record(state: dict[str, Any]) -> dict[str, Any] | None:
    value = _number(state)
    if value is None:
        return None
    return {
        "entity_id": str(state.get("entity_id") or ""),
        "name": _friendly_name(state),
        "value": round(value, 1),
        "unit": _unit(state),
    }


def _presence_state_is_usable(state: dict[str, Any]) -> bool:
    return str(state.get("state") or "").strip().casefold() in _VALID_PRESENCE_STATES


def _is_vehicle_presence(state: dict[str, Any]) -> bool:
    searchable = f"{state.get('entity_id', '')} {_friendly_name(state)}".casefold()
    return any(term in searchable for term in _IGNORED_PRESENCE_TERMS)


class HomeAssistantIntegration(Integration):
    name = "home_assistant"
    label = "Home Assistant"

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float,
        temperature_entities: str = "",
        presence_entities: str = "",
        selected_entities: str = "",
        max_temperature_sensors: int = 6,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token.strip()
        self.timeout = timeout
        self.temperature_entities = _split_entities(temperature_entities)
        self.presence_entities = _split_entities(presence_entities)
        self.selected_entities = _split_entities(selected_entities)
        self.max_temperature_sensors = max_temperature_sensors
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.token)

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

    async def _states(self) -> list[dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=headers,
            transport=self.transport,
            follow_redirects=True,
        ) as client:
            response = await client.get("/api/states")
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Home Assistant states payload is not a list")
        return [item for item in payload if isinstance(item, dict)]

    @staticmethod
    def _configured_records(
        index: dict[str, dict[str, Any]],
        entity_ids: tuple[str, ...],
        missing: list[str],
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for entity_id in entity_ids:
            state = index.get(entity_id)
            if state is None:
                missing.append(entity_id)
                continue
            records.append(_generic_record(state))
        return records

    def _presence_records(
        self,
        states: list[dict[str, Any]],
        index: dict[str, dict[str, Any]],
        missing: list[str],
    ) -> list[dict[str, Any]]:
        if self.presence_entities:
            records: list[dict[str, Any]] = []
            for entity_id in self.presence_entities:
                state = index.get(entity_id)
                if state is None:
                    missing.append(entity_id)
                    continue
                if _presence_state_is_usable(state):
                    records.append(_generic_record(state))
            return records

        people = [
            _generic_record(state)
            for state in states
            if str(state.get("entity_id") or "").startswith("person.")
            and _presence_state_is_usable(state)
            and not _is_vehicle_presence(state)
        ]
        if people:
            return sorted(people, key=lambda item: str(item["name"]).casefold())[:8]

        trackers = [
            _generic_record(state)
            for state in states
            if str(state.get("entity_id") or "").startswith("device_tracker.")
            and _presence_state_is_usable(state)
            and not _is_vehicle_presence(state)
        ]
        return sorted(trackers, key=lambda item: str(item["name"]).casefold())[:8]

    def _temperature_records(
        self,
        states: list[dict[str, Any]],
        index: dict[str, dict[str, Any]],
        missing: list[str],
    ) -> list[dict[str, Any]]:
        if self.temperature_entities:
            records: list[dict[str, Any]] = []
            for entity_id in self.temperature_entities:
                state = index.get(entity_id)
                if state is None:
                    missing.append(entity_id)
                    continue
                record = _temperature_record(state)
                if record is not None:
                    records.append(record)
            return records

        candidates: list[dict[str, Any]] = []
        for state in states:
            attrs = _attrs(state)
            if str(attrs.get("device_class") or "").casefold() != "temperature":
                continue
            searchable = f"{state.get('entity_id', '')} {_friendly_name(state)}".casefold()
            if any(term in searchable for term in _IGNORED_TEMPERATURE_TERMS):
                continue
            record = _temperature_record(state)
            if record is not None:
                candidates.append(record)
        candidates.sort(key=lambda item: str(item["name"]).casefold())
        return candidates[: self.max_temperature_sensors]

    async def snapshot(self) -> IntegrationSnapshot:
        if not self.base_url:
            return self.unavailable("Set HA_BASE_URL to connect Home Assistant.")
        if not self.token:
            return self.unavailable("Set HA_TOKEN to connect Home Assistant.")

        try:
            states = await self._states()
        except (httpx.HTTPError, ValueError) as exc:
            return self.unavailable(f"Home Assistant request failed: {type(exc).__name__}")

        index = {
            str(state.get("entity_id")): state
            for state in states
            if state.get("entity_id")
        }
        missing: list[str] = []
        presence = self._presence_records(states, index, missing)
        temperatures = self._temperature_records(states, index, missing)
        selected = self._configured_records(index, self.selected_entities, missing)
        people_home = sum(1 for person in presence if str(person.get("state")) == "home")
        observed_values = [
            str(state.get("last_updated"))
            for state in states
            if state.get("last_updated")
        ]
        observed_at = max(observed_values, default=None)
        status = "degraded" if missing else "online"
        detail = "Home Assistant"
        if missing:
            noun = "entity" if len(missing) == 1 else "entities"
            detail = f"Home Assistant • {len(missing)} configured {noun} missing"

        return IntegrationSnapshot(
            name=self.name,
            label=self.label,
            configured=True,
            healthy=True,
            status=status,
            metrics={
                "people_home": people_home,
                "people_total": len(presence),
                "temperature_count": len(temperatures),
                "selected_count": len(selected),
                "entity_count": len(states),
                "presence": presence,
                "temperatures": temperatures,
                "selected": selected,
                "missing_entities": sorted(set(missing)),
            },
            detail=detail,
            link=self.base_url,
            observed_at=observed_at,
        )
