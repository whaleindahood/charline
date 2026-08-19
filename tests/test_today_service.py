from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

from plugins.charline.today import TodayService


def test_today_reads_sources_once_and_builds_without_llm():
    projects = SimpleNamespace(list=MagicMock(return_value=[SimpleNamespace(name="Site")]))
    data = SimpleNamespace(
        personal_tasks=MagicMock(return_value=[{"title": "Купить лампу"}]),
        upcoming_reminders=MagicMock(return_value=[{"name": "Weekly review"}]),
    )
    calendar = SimpleNamespace(list_between=AsyncMock(return_value=[{
        "summary": "Созвон", "start": "2026-08-20T14:00:00+03:00"
    }]))
    service = TodayService(
        projects, data, calendar_reader=calendar,
        now=lambda: datetime(2026, 8, 20, 9, 0, tzinfo=ZoneInfo("Europe/Moscow")),
        timezone_loader=lambda: "Europe/Moscow",
    )
    card = asyncio.run(service.card(SimpleNamespace(chat_id="123", thread_id=None)))

    assert "14:00 · Созвон" in card["text"]
    assert "Купить лампу" in card["text"]
    assert "Weekly review" in card["text"]
    assert "Проектных тем: 1" in card["text"]
    assert "Проверено: 09:00 · Europe/Moscow" in card["text"]
    calendar.list_between.assert_awaited_once()
    data.personal_tasks.assert_called_once_with()
    projects.list.assert_called_once_with("123")
    data.upcoming_reminders.assert_called_once()
