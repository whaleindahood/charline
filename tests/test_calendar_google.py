from __future__ import annotations

import asyncio
import json

from plugins.charline.calendar_google import GoogleCalendarExecutor


EVENT = {
    "title": "Прогулка",
    "start": "2026-08-21T14:00:00+03:00",
    "end": "2026-08-21T15:30:00+03:00",
    "timezone": "Europe/Moscow",
}


def _listed(event_id="event-1"):
    return json.dumps([{
        "id": event_id,
        "summary": EVENT["title"],
        "start": EVENT["start"],
        "end": EVENT["end"],
        "htmlLink": "https://calendar.google.com/event-1",
    }])


def test_success_is_verified_by_narrow_readback():
    responses = [
        (0, json.dumps({"status": "created", "id": "event-1"}), "", False),
        (0, _listed(), "", False),
    ]

    async def run(argv, timeout):
        del argv, timeout
        return responses.pop(0)

    result = asyncio.run(GoogleCalendarExecutor(command_runner=run, script_path="google_api.py").execute(EVENT))
    assert result.status == "completed"
    assert result.external_resource_id == "event-1"


def test_definite_google_rejection_is_failed():
    async def run(argv, timeout):
        del argv, timeout
        return 1, "", "HTTP 400 invalid event", False

    result = asyncio.run(GoogleCalendarExecutor(command_runner=run, script_path="google_api.py").execute(EVENT))
    assert result.status == "failed"


def test_timeout_without_reconciliation_match_is_unknown_and_not_retried():
    calls = []

    async def run(argv, timeout):
        calls.append(argv)
        if len(calls) == 1:
            return -1, "", "timeout", True
        return 0, "[]", "", False

    result = asyncio.run(GoogleCalendarExecutor(command_runner=run, script_path="google_api.py").execute(EVENT))
    assert result.status == "unknown"
    assert len(calls) == 2
    assert calls[0][2:4] == ["calendar", "create"]
    assert calls[1][2:4] == ["calendar", "list"]


def test_timeout_with_reconciliation_match_is_completed():
    responses = [(-1, "", "timeout", True), (0, _listed("reconciled"), "", False)]

    async def run(argv, timeout):
        del argv, timeout
        return responses.pop(0)

    result = asyncio.run(GoogleCalendarExecutor(command_runner=run, script_path="google_api.py").execute(EVENT))
    assert result.status == "completed"
    assert result.external_resource_id == "reconciled"
