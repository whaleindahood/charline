"""Pure construction of explicit Hermes cron/reminder drafts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ReminderError(ValueError):
    """Raised when a reminder draft is incomplete or unsafe to schedule."""


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_reminder_draft(
    *,
    message: str,
    schedule: str,
    schedule_type: str,
    timezone_name: str,
    destination: str,
    now: datetime,
) -> dict[str, object]:
    """Return a self-contained cron creation draft; never schedules it."""

    message = message.strip()
    schedule = schedule.strip()
    schedule_type = schedule_type.strip().lower()
    destination = destination.strip()
    if not message or not destination or not schedule:
        raise ReminderError("message, schedule and destination are required")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ReminderError("now must be timezone-aware")
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ReminderError(f"unknown timezone: {timezone_name}") from exc

    if schedule_type == "once":
        try:
            trigger = datetime.fromisoformat(schedule.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ReminderError("once schedule must be an ISO-8601 timestamp") from exc
        if trigger.tzinfo is None or trigger.utcoffset() is None:
            raise ReminderError("once schedule must be timezone-aware")
        if trigger.astimezone(timezone.utc) <= now.astimezone(timezone.utc):
            raise ReminderError("once schedule must be in the future")
    elif schedule_type == "cron":
        if len(schedule.split()) != 5:
            raise ReminderError("cron schedule must contain five fields")
    else:
        raise ReminderError("schedule_type must be once or cron")

    identity = {
        "message": message,
        "schedule": schedule,
        "schedule_type": schedule_type,
        "timezone": timezone_name,
        "destination": destination,
    }
    idempotency_key = hashlib.sha256(_canonical(identity).encode("utf-8")).hexdigest()
    job_prompt = (
        "Reminder job. Send exactly this user-authored reminder to "
        f"{destination}: {_canonical(message)}. "
        f"Idempotency key: {idempotency_key}. "
        "Before delivery, check whether this idempotency key was already delivered; "
        "do not duplicate it. Do not change the destination or perform other writes."
    )
    return {
        "schema_version": 1,
        "operation": "hermes.cron.create",
        "effect": "external_write",
        "message": message,
        "schedule": {"type": schedule_type, "value": schedule, "timezone": timezone_name},
        "delivery": {"destination": destination},
        "idempotency_key": idempotency_key,
        "job_prompt": job_prompt,
        "preview": (
            f"Create {schedule_type} reminder at {schedule} ({timezone_name}) to "
            f"{destination}: {message}"
        ),
    }

