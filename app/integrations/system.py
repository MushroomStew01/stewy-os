from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import psutil

from .base import Integration, IntegrationSnapshot


def _temperature_c() -> float | None:
    candidates = [
        Path("/sys/class/thermal/thermal_zone0/temp"),
        Path("/sys/class/hwmon/hwmon0/temp1_input"),
    ]
    for path in candidates:
        try:
            raw = float(path.read_text().strip())
            return round(raw / 1000 if raw > 200 else raw, 1)
        except (OSError, ValueError):
            continue
    try:
        readings = psutil.sensors_temperatures(fahrenheit=False)
    except (AttributeError, OSError):
        return None
    for entries in readings.values():
        if entries:
            return round(float(entries[0].current), 1)
    return None


class SystemIntegration(Integration):
    name = "system"
    label = "HomeLab"

    async def snapshot(self) -> IntegrationSnapshot:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        boot = datetime.fromtimestamp(psutil.boot_time(), tz=UTC)
        uptime_seconds = max(0, int((datetime.now(UTC) - boot).total_seconds()))
        load = os.getloadavg()[0] if hasattr(os, "getloadavg") else None
        return IntegrationSnapshot(
            name=self.name,
            label=self.label,
            configured=True,
            healthy=True,
            status="online",
            metrics={
                "cpu_percent": round(psutil.cpu_percent(interval=None), 1),
                "memory_percent": round(float(memory.percent), 1),
                "disk_percent": round(float(disk.percent), 1),
                "temperature_c": _temperature_c(),
                "uptime_seconds": uptime_seconds,
                "load_1m": round(float(load), 2) if load is not None else None,
            },
            detail="Stewy OS host",
            observed_at=datetime.now(UTC).isoformat(),
        )
