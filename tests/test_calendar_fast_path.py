from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from plugins.charline.calendar_fast_path import (
    DraftIncomplete,
    PendingActionStore,
    is_exact_calendar_candidate,
    resolve_calendar_draft,
)


def _draft(**overrides):
    draft = {
        "intent": "calendar_create",
        "title": "Прогулка",
        "date": {"type": "relative_day", "offset": 1},
        "time": {"type": "local_time", "value": "14:00"},
        "duration_minutes": 90,
        "timezone": None,
        "missing_fields": [],
    }
    draft.update(overrides)
    return draft


def test_resolves_tomorrow_and_ninety_minutes_from_fresh_runtime_time():
    now = datetime(2026, 8, 20, 23, 55, tzinfo=ZoneInfo("Europe/Moscow"))
    event = resolve_calendar_draft(_draft(), now=now, profile_timezone="Europe/Moscow")
    assert event.start.isoformat() == "2026-08-21T14:00:00+03:00"
    assert event.end.isoformat() == "2026-08-21T15:30:00+03:00"


def test_next_friday_is_strictly_in_the_future():
    now = datetime(2026, 8, 21, 9, 0, tzinfo=ZoneInfo("Europe/Moscow"))  # Friday
    event = resolve_calendar_draft(_draft(
        date={"type": "relative_weekday", "weekday": "friday", "direction": "next"}
    ), now=now, profile_timezone="Europe/Moscow")
    assert event.start.date().isoformat() == "2026-08-28"


def test_relative_duration_starts_in_three_hours():
    now = datetime(2026, 8, 20, 10, 15, tzinfo=ZoneInfo("Asia/Tbilisi"))
    event = resolve_calendar_draft(_draft(
        date={"type": "relative_duration", "minutes": 180},
        time=None,
        duration_minutes=60,
    ), now=now, profile_timezone="Asia/Tbilisi")
    assert event.start.isoformat() == "2026-08-20T13:15:00+04:00"


def test_explicit_timezone_overrides_profile_timezone():
    now = datetime(2026, 8, 20, 9, 0, tzinfo=ZoneInfo("UTC"))
    event = resolve_calendar_draft(
        _draft(timezone="America/New_York"), now=now, profile_timezone="Europe/Moscow"
    )
    assert event.start.tzinfo.key == "America/New_York"
    assert event.start.utcoffset().total_seconds() == -4 * 3600


def test_nonexistent_dst_wall_time_is_rejected():
    now = datetime(2026, 3, 7, 9, 0, tzinfo=ZoneInfo("America/New_York"))
    with pytest.raises(ValueError, match="DST"):
        resolve_calendar_draft(_draft(
            date={"type": "absolute_date", "value": "2026-03-08"},
            time={"type": "local_time", "value": "02:30"},
            timezone="America/New_York",
        ), now=now, profile_timezone="America/New_York")


def test_missing_parameters_are_reported_without_guessing():
    with pytest.raises(DraftIncomplete) as exc:
        resolve_calendar_draft(_draft(duration_minutes=None, missing_fields=["duration_minutes"]),
                               now=datetime.now(ZoneInfo("UTC")), profile_timezone="UTC")
    assert exc.value.fields == ("duration_minutes",)


@pytest.mark.parametrize("text", [
    "Запиши прогулку завтра в 14 на полтора часа",
    "Добавь стоматолога в пятницу в 10:30",
    "Поставь на завтра с 18 до 19 тренировку",
])
def test_exact_creation_candidate(text):
    assert is_exact_calendar_candidate(text)


@pytest.mark.parametrize("text", [
    "Найди завтра полтора часа для тренировки",
    "Когда у меня есть окно для встречи?",
    "Подбери время между звонками",
    "Расскажи про пятницу",
])
def test_scheduling_and_general_requests_are_not_fast_candidates(text):
    assert not is_exact_calendar_candidate(text)


class FakeState:
    def __init__(self):
        self.value = {}

    def get(self, key, default=None):
        return self.value.get(key, default)

    def set(self, key, value):
        self.value[key] = value


def test_pending_action_claim_is_durable_owner_bound_and_once_only():
    state = FakeState()
    store = PendingActionStore(state, now=lambda: 1_000.0, ttl_seconds=600)
    action_id = store.create(
        owner_user_id="42", chat_id="123", thread_id="", payload={"title": "Walk"}
    )
    assert store.claim(action_id, owner_user_id="99", chat_id="123", thread_id="") is None
    claimed = store.claim(action_id, owner_user_id="42", chat_id="123", thread_id="")
    assert claimed["status"] == "executing"
    assert store.claim(action_id, owner_user_id="42", chat_id="123", thread_id="") is None

    restarted = PendingActionStore(state, now=lambda: 1_001.0, ttl_seconds=600)
    restarted.complete(action_id, external_resource_id="event-1")
    assert restarted.get(action_id)["external_resource_id"] == "event-1"


def test_cancel_and_expiry_never_claim():
    state = FakeState()
    clock = SimpleNamespace(value=1_000.0)
    store = PendingActionStore(state, now=lambda: clock.value, ttl_seconds=10)
    cancelled = store.create(owner_user_id="42", chat_id="123", thread_id="7", payload={})
    assert store.cancel(cancelled, owner_user_id="42", chat_id="123", thread_id="7")
    assert store.claim(cancelled, owner_user_id="42", chat_id="123", thread_id="7") is None

    expired = store.create(owner_user_id="42", chat_id="123", thread_id="7", payload={})
    clock.value += 11
    assert store.claim(expired, owner_user_id="42", chat_id="123", thread_id="7") is None
    assert store.get(expired)["status"] == "cancelled"
