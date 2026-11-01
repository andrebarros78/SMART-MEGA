"""Draw-time guards shared by operator-owned missed-recovery flows.

No historical result is fetched or written here. The caller retains all
certification, authorization, proof persistence and recovery rollback gates.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable


def assert_missed_draw_elapsed(
    schedule: dict[str, Any] | None,
    now_utc: datetime | None,
    *,
    mode: str,
    clock_now: Callable[[], datetime],
) -> None:
    """Preserve the pre-existing unprepared and unfrozen recovery time gates."""
    if mode == "unprepared":
        scheduled_raw = schedule.get("scheduled_datetime")
        if not isinstance(scheduled_raw, str):
            raise ValueError("unprepared missed-target recovery requires scheduled draw authority")
    elif mode == "unfrozen":
        if not isinstance(schedule, dict) or not isinstance(schedule.get("scheduled_datetime"), str):
            raise ValueError("missed-target recovery requires scheduled draw authority")
        scheduled_raw = schedule["scheduled_datetime"]
    else:
        raise ValueError("unsupported missed-target recovery mode")

    scheduled = datetime.fromisoformat(scheduled_raw)
    if mode == "unprepared":
        if scheduled.tzinfo is None or scheduled.utcoffset() is None:
            raise ValueError("scheduled draw authority must be timezone-aware")
    elif scheduled.tzinfo is None:
        raise ValueError("scheduled draw authority must be timezone-aware")

    observed_now = now_utc if now_utc is not None else clock_now()
    if mode == "unprepared":
        if observed_now.tzinfo is None or observed_now.utcoffset() is None:
            raise ValueError("missed-target recovery clock must be timezone-aware")
    elif observed_now.tzinfo is None:
        raise ValueError("missed-target recovery clock must be timezone-aware")
    if observed_now.astimezone(timezone.utc) <= scheduled.astimezone(timezone.utc):
        raise ValueError("missed-target recovery is forbidden before the scheduled draw")
