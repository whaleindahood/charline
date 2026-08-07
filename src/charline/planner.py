"""Deterministic interval subtraction for calendar availability."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

Interval = tuple[datetime, datetime]
UTC = timezone.utc


def _aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def find_free_slots(
    *,
    window_start: datetime,
    window_end: datetime,
    duration: timedelta,
    busy: Iterable[Interval],
    buffer: timedelta = timedelta(0),
    limit: int = 3,
) -> list[Interval]:
    """Return non-overlapping slots using elapsed-time arithmetic in UTC.

    Results are converted back to the timezone object of ``window_start``.
    Meeting duration is intentionally also the start granularity.
    """
    _aware(window_start, "window_start")
    _aware(window_end, "window_end")
    if duration <= timedelta(0):
        raise ValueError("duration must be positive")
    if buffer < timedelta(0):
        raise ValueError("buffer cannot be negative")
    if limit < 0:
        raise ValueError("limit cannot be negative")

    output_tz = window_start.tzinfo
    start_utc, end_utc = _utc(window_start), _utc(window_end)
    if end_utc <= start_utc:
        raise ValueError("window_end must be after window_start")
    if limit == 0:
        return []

    blocked: list[Interval] = []
    for index, (start, end) in enumerate(busy):
        _aware(start, f"busy[{index}].start")
        _aware(end, f"busy[{index}].end")
        start, end = _utc(start), _utc(end)
        if end <= start:
            raise ValueError(f"busy[{index}] end must be after start")
        start = max(start_utc, start - buffer)
        end = min(end_utc, end + buffer)
        if start < end:
            blocked.append((start, end))

    blocked.sort(key=lambda interval: interval[0])
    merged: list[list[datetime]] = []
    for start, end in blocked:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    slots: list[Interval] = []
    cursor = start_utc
    for blocked_start, blocked_end in [*merged, [end_utc, end_utc]]:
        while cursor + duration <= blocked_start and len(slots) < limit:
            slot_end = cursor + duration
            slots.append(
                (cursor.astimezone(output_tz), slot_end.astimezone(output_tz))
            )
            cursor = slot_end
        if len(slots) >= limit:
            break
        cursor = max(cursor, blocked_end)
    return slots
