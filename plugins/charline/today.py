"""Parallel deterministic Today read model."""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .calendar_google import GoogleCalendarReader


def _button(label: str, action: str) -> dict[str, str]:
    return {"label": label, "action": action}


class TodayService:
    def __init__(
        self,
        projects: Any,
        data: Any,
        *,
        calendar_reader: Any = None,
        now,
        timezone_loader,
    ):
        self._projects = projects
        self._data = data
        self._calendar = calendar_reader or GoogleCalendarReader()
        self._now = now
        self._timezone_loader = timezone_loader

    async def card(self, source: Any) -> dict[str, Any]:
        timezone_name = self._timezone_loader()
        runtime_now = self._now()
        try:
            zone = ZoneInfo(timezone_name)
        except Exception:
            zone = runtime_now.tzinfo
            timezone_name = str(getattr(zone, "key", zone) or "не настроен")
        local_now = runtime_now.astimezone(zone)
        start = datetime.combine(local_now.date(), time.min, tzinfo=zone)
        end = start + timedelta(days=1)
        events, tasks, projects, reminders = await asyncio.gather(
            self._calendar.list_between(start, end),
            asyncio.to_thread(self._data.personal_tasks),
            asyncio.to_thread(self._projects.list, str(source.chat_id)),
            asyncio.to_thread(self._data.upcoming_reminders, source),
        )
        lines = ["Сегодня"]
        if events:
            lines.extend(["", "Ближайшие события"])
            for item in events[:3]:
                try:
                    starts = datetime.fromisoformat(str(item.get("start") or "").replace("Z", "+00:00"))
                    when = starts.astimezone(zone).strftime("%H:%M")
                except ValueError:
                    when = "время не указано"
                lines.append(f"• {when} · {item.get('summary') or 'Без названия'}")
        if tasks:
            lines.extend(["", "Задачи", *(f"• {item['title']}" for item in tasks[:3])])
            if len(tasks) > 3:
                lines.append(f"Ещё: {len(tasks) - 3}")
        if reminders:
            lines.extend(["", "Ближайшие напоминания"])
            lines.extend(f"• {item['name']}" for item in reminders[:3])
        if projects:
            lines.extend(["", f"Проектных тем: {len(projects)}"])
        if not any((events, tasks, projects, reminders)):
            lines.extend(["", "Пока нет событий, задач, напоминаний или проектов."])
        unavailable = [
            name for name, value in (
                ("Календарь", events), ("Задачи", tasks), ("Напоминания", reminders)
            ) if value is None
        ]
        if unavailable:
            lines.extend(["", "Недоступно: " + ", ".join(unavailable)])
        lines.extend(["", f"Проверено: {local_now:%H:%M} · {timezone_name}"])
        return {
            "text": "\n".join(lines),
            "buttons": [[_button("Задачи", "personal_tasks"), _button("Проекты", "projects")], [_button("Назад", "home")]],
        }
