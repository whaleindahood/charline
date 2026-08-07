"""Normalized JSON contract for deterministic calendar availability planning."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

from charline.planner import find_free_slots


class AvailabilityValidationError(ValueError):
    pass


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise AvailabilityValidationError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise AvailabilityValidationError(f"{label} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AvailabilityValidationError(f"{label} must be timezone-aware")
    return parsed


def _nonnegative_int(value: object, label: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AvailabilityValidationError(f"{label} must be an integer")
    if positive and value <= 0:
        raise AvailabilityValidationError(f"{label} must be positive")
    if not positive and value < 0:
        raise AvailabilityValidationError(f"{label} cannot be negative")
    return value


def plan_availability(request: Mapping[str, object]) -> dict[str, object]:
    """Validate normalized source data and return timezone-aware free slots."""
    if not isinstance(request, Mapping):
        raise AvailabilityValidationError("request must be an object")
    window_start = _timestamp(request.get("window_start"), "window_start")
    window_end = _timestamp(request.get("window_end"), "window_end")
    current_time = _timestamp(request.get("current_time"), "current_time")
    duration_minutes = _nonnegative_int(
        request.get("duration_minutes"), "duration_minutes", positive=True
    )
    buffer_minutes = _nonnegative_int(
        request.get("buffer_minutes", 0), "buffer_minutes"
    )
    limit = _nonnegative_int(request.get("limit", 3), "limit")
    raw_busy = request.get("busy", [])
    if not isinstance(raw_busy, list):
        raise AvailabilityValidationError("busy must be a list")

    if window_end.astimezone(timezone.utc) <= window_start.astimezone(timezone.utc):
        raise AvailabilityValidationError("window_end must be after window_start")
    effective_start = max(
        window_start.astimezone(timezone.utc), current_time.astimezone(timezone.utc)
    ).astimezone(window_start.tzinfo)
    if effective_start.astimezone(timezone.utc) >= window_end.astimezone(timezone.utc):
        slots = []
    else:
        busy = []
        for index, interval in enumerate(raw_busy):
            if not isinstance(interval, Mapping):
                raise AvailabilityValidationError(f"busy[{index}] must be an object")
            busy.append(
                (
                    _timestamp(interval.get("start"), f"busy[{index}].start"),
                    _timestamp(interval.get("end"), f"busy[{index}].end"),
                )
            )
        slots = find_free_slots(
            window_start=effective_start,
            window_end=window_end,
            duration=timedelta(minutes=duration_minutes),
            busy=busy,
            buffer=timedelta(minutes=buffer_minutes),
            limit=limit,
        )

    return {
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "effective_start": effective_start.isoformat(),
        "duration_minutes": duration_minutes,
        "buffer_minutes": buffer_minutes,
        "slots": [
            {"start": start.isoformat(), "end": end.isoformat()}
            for start, end in slots
        ],
    }
