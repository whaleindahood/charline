"""Deterministic domain logic for one narrow Calendar create fast path."""

from __future__ import annotations

import copy
import re
import secrets
import threading
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


class DraftIncomplete(ValueError):
    def __init__(self, fields: list[str] | tuple[str, ...]):
        self.fields = tuple(dict.fromkeys(str(item) for item in fields if item))
        super().__init__("missing calendar fields: " + ", ".join(self.fields))


@dataclass(frozen=True)
class ResolvedCalendarEvent:
    title: str
    start: datetime
    end: datetime
    timezone: str

    def payload(self) -> dict[str, str]:
        return {
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "timezone": self.timezone,
        }


def is_exact_calendar_candidate(text: str) -> bool:
    """Cheap narrow gate; the structured parser remains authoritative."""
    normalized = " ".join(str(text or "").casefold().split())
    if not normalized or re.search(r"\b(найди|подбери|когда|окно|свободн)", normalized):
        return False
    create = re.search(
        r"\b(запиш\w*|добав\w*|постав\w*|созда\w*\s+событ\w*|add|schedule)\b",
        normalized,
    )
    temporal = re.search(
        r"(\d{1,2}[:.]\d{2}|\bв\s+\d{1,2}\b|завтра|послезавтра|"
        r"понедельник|вторник|сред\w*|четверг|пятниц\w*|суббот\w*|воскресень\w*|через)",
        normalized,
    )
    return bool(create and temporal)


def _parse_wall_time(raw: Any, field: str) -> time:
    try:
        return time.fromisoformat(str(raw))
    except (TypeError, ValueError) as exc:
        raise DraftIncomplete([field]) from exc


def _valid_local_datetime(day: date, wall_time: time, zone: ZoneInfo) -> datetime:
    naive = datetime.combine(day, wall_time.replace(tzinfo=None))
    candidates = []
    for fold in (0, 1):
        local = naive.replace(tzinfo=zone, fold=fold)
        roundtrip = local.astimezone(timezone.utc).astimezone(zone)
        if roundtrip.replace(tzinfo=None) == naive:
            candidates.append(local)
    if not candidates:
        raise ValueError("local time does not exist because of a DST transition")
    offsets = {item.utcoffset() for item in candidates}
    if len(offsets) > 1:
        raise ValueError("local time is ambiguous because of a DST transition")
    return candidates[0]


def _resolve_day(spec: Mapping[str, Any], local_now: datetime) -> date:
    kind = str(spec.get("type") or "")
    if kind == "absolute_date":
        try:
            return date.fromisoformat(str(spec.get("value") or ""))
        except ValueError as exc:
            raise DraftIncomplete(["date"]) from exc
    if kind == "relative_day":
        try:
            return local_now.date() + timedelta(days=int(spec.get("offset")))
        except (TypeError, ValueError) as exc:
            raise DraftIncomplete(["date"]) from exc
    if kind == "relative_weekday":
        weekday = WEEKDAYS.get(str(spec.get("weekday") or "").casefold())
        if weekday is None:
            raise DraftIncomplete(["date"])
        delta = (weekday - local_now.weekday()) % 7
        if str(spec.get("direction") or "next") == "next" and delta == 0:
            delta = 7
        return local_now.date() + timedelta(days=delta)
    raise DraftIncomplete(["date"])


def resolve_calendar_draft(
    draft: Mapping[str, Any], *, now: datetime, profile_timezone: str
) -> ResolvedCalendarEvent:
    """Resolve a parser draft using fresh runtime time and IANA timezone data."""
    if str(draft.get("intent") or "") != "calendar_create":
        raise ValueError("not an exact Calendar create draft")
    missing = list(draft.get("missing_fields") or [])
    title = " ".join(str(draft.get("title") or "").split())
    if not title:
        missing.append("title")
    timezone_name = str(draft.get("timezone") or profile_timezone or "").strip()
    if not timezone_name:
        missing.append("timezone")
    try:
        zone = ZoneInfo(timezone_name) if timezone_name else None
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown IANA timezone: {timezone_name}") from exc
    if missing:
        raise DraftIncomplete(missing)
    assert zone is not None
    local_now = now.astimezone(zone)
    date_spec = draft.get("date")
    if not isinstance(date_spec, Mapping):
        raise DraftIncomplete(["date"])

    if str(date_spec.get("type") or "") == "relative_duration":
        try:
            start = local_now + timedelta(minutes=int(date_spec.get("minutes")))
        except (TypeError, ValueError) as exc:
            raise DraftIncomplete(["date"]) from exc
    else:
        day = _resolve_day(date_spec, local_now)
        time_spec = draft.get("time")
        if not isinstance(time_spec, Mapping) or time_spec.get("type") != "local_time":
            raise DraftIncomplete(["time"])
        start = _valid_local_datetime(day, _parse_wall_time(time_spec.get("value"), "time"), zone)

    duration = draft.get("duration_minutes")
    end_time_raw = draft.get("end_time")
    if duration is not None:
        try:
            minutes = int(duration)
        except (TypeError, ValueError) as exc:
            raise DraftIncomplete(["duration_minutes"]) from exc
        if minutes <= 0:
            raise ValueError("duration must be positive")
        end = start + timedelta(minutes=minutes)
    elif end_time_raw:
        end = _valid_local_datetime(
            start.date(), _parse_wall_time(end_time_raw, "end_time"), zone
        )
        if end <= start:
            end = _valid_local_datetime(
                start.date() + timedelta(days=1),
                _parse_wall_time(end_time_raw, "end_time"),
                zone,
            )
    else:
        raise DraftIncomplete(["duration_minutes"])
    return ResolvedCalendarEvent(title=title, start=start, end=end, timezone=timezone_name)


class PendingActionStore:
    """Atomic-enough single-Gateway state over Hermes' existing plugin state."""

    KEY = "calendar_actions"
    TERMINAL = {"completed", "cancelled", "failed", "unknown"}

    def __init__(
        self,
        state: Any,
        *,
        now: Callable[[], float],
        ttl_seconds: int = 600,
        max_actions: int = 128,
    ):
        self._state = state
        self._now = now
        self._ttl = ttl_seconds
        self._max = max_actions
        self._lock = threading.Lock()

    def _load(self) -> dict[str, dict[str, Any]]:
        raw = self._state.get(self.KEY, {})
        return copy.deepcopy(raw) if isinstance(raw, dict) else {}

    def _save(self, actions: dict[str, dict[str, Any]]) -> None:
        if len(actions) > self._max:
            ordered = sorted(actions.items(), key=lambda item: float(item[1].get("created_at", 0)))
            for action_id, item in ordered:
                if len(actions) <= self._max:
                    break
                if item.get("status") in self.TERMINAL:
                    actions.pop(action_id, None)
            while len(actions) > self._max:
                actions.pop(next(iter(actions)))
        self._state.set(self.KEY, actions)

    def create(
        self, *, owner_user_id: str, chat_id: str, thread_id: str, payload: Mapping[str, Any]
    ) -> str:
        with self._lock:
            actions = self._load()
            action_id = secrets.token_hex(8)
            actions[action_id] = {
                "action_id": action_id,
                "owner_user_id": str(owner_user_id),
                "chat_id": str(chat_id),
                "thread_id": str(thread_id or ""),
                "payload": copy.deepcopy(dict(payload)),
                "created_at": self._now(),
                "status": "pending",
                "external_resource_id": "",
            }
            self._save(actions)
            return action_id

    def get(self, action_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._load().get(action_id)
            return copy.deepcopy(item) if item else None

    @staticmethod
    def _owns(item: Mapping[str, Any], owner_user_id: str, chat_id: str, thread_id: str) -> bool:
        return (
            item.get("owner_user_id") == str(owner_user_id)
            and item.get("chat_id") == str(chat_id)
            and item.get("thread_id") == str(thread_id or "")
        )

    def claim(
        self,
        action_id: str,
        *,
        owner_user_id: str,
        chat_id: str,
        thread_id: str,
        message_id: str = "",
    ):
        with self._lock:
            actions = self._load()
            item = actions.get(action_id)
            if not item or not self._owns(item, owner_user_id, chat_id, thread_id):
                return None
            if item.get("status") != "pending":
                return None
            if self._now() - float(item.get("created_at", 0)) > self._ttl:
                item["status"] = "cancelled"
                item["error"] = "expired"
                self._save(actions)
                return None
            item["status"] = "executing"
            item["execution_started_at"] = self._now()
            item["message_id"] = str(message_id or "")
            self._save(actions)
            return copy.deepcopy(item)

    def mark_external_started(self, action_id: str) -> None:
        with self._lock:
            actions = self._load()
            item = actions.get(action_id)
            if not item or item.get("status") != "executing":
                return
            item["external_started_at"] = self._now()
            self._save(actions)

    def recoverable(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                copy.deepcopy(item)
                for item in self._load().values()
                if item.get("status") == "executing"
            ]

    def cancel(self, action_id: str, *, owner_user_id: str, chat_id: str, thread_id: str) -> bool:
        with self._lock:
            actions = self._load()
            item = actions.get(action_id)
            if (
                not item
                or not self._owns(item, owner_user_id, chat_id, thread_id)
                or item.get("status") != "pending"
            ):
                return False
            item["status"] = "cancelled"
            self._save(actions)
            return True

    def _finish(self, action_id: str, status: str, **fields: Any) -> None:
        with self._lock:
            actions = self._load()
            item = actions.get(action_id)
            if not item or item.get("status") not in {"executing", "unknown"}:
                return
            item.update(fields)
            item["status"] = status
            item["finished_at"] = self._now()
            self._save(actions)

    def complete(self, action_id: str, *, external_resource_id: str) -> None:
        self._finish(action_id, "completed", external_resource_id=str(external_resource_id))

    def fail(self, action_id: str, *, error: str) -> None:
        self._finish(action_id, "failed", error=str(error)[:512])

    def mark_unknown(self, action_id: str, *, error: str) -> None:
        self._finish(action_id, "unknown", error=str(error)[:512])
