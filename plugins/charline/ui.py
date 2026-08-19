"""Minimal, reconstructable Telegram views over Hermes-owned state."""

from __future__ import annotations

import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable

from .projects import NativeProject, ProjectService


CONFIRM_TTL_SECONDS = 600
PROJECT_PAGE_SIZE = 8
PERSONAL_TASK_PREFIX = "Задача: "


@dataclass(frozen=True)
class UiContext:
    source: Any


def _button(label: str, action: str) -> dict[str, str]:
    return {"label": label, "action": action}


class HermesUiData:
    """Narrow facade over native Hermes state; it persists nothing."""

    @staticmethod
    def memory_entries() -> list[dict[str, str]] | None:
        try:
            from tools.memory_tool import load_on_disk_store

            store = load_on_disk_store()
            pairs = [
                *(("user", item) for item in store.user_entries),
                *(("memory", item) for item in store.memory_entries),
            ]
            return [
                {
                    "target": target,
                    "content": content,
                    "digest": sha256(f"{target}\0{content}".encode()).hexdigest()[:12],
                }
                for target, content in pairs
            ]
        except Exception:
            return None

    @classmethod
    def personal_tasks(cls) -> list[dict[str, str]] | None:
        entries = cls.memory_entries()
        if entries is None:
            return None
        return [
            {
                "title": entry["content"][len(PERSONAL_TASK_PREFIX):].strip(),
                "target": entry["target"],
                "digest": entry["digest"],
            }
            for entry in entries
            if entry["content"].startswith(PERSONAL_TASK_PREFIX)
            and entry["content"][len(PERSONAL_TASK_PREFIX):].strip()
        ]

    @staticmethod
    def delete_memory(target: str, digest: str) -> bool:
        try:
            from tools.memory_tool import load_on_disk_store, save_on_disk_store

            store = load_on_disk_store()
            entries = store.user_entries if target == "user" else store.memory_entries
            match = next(
                (
                    item for item in entries
                    if sha256(f"{target}\0{item}".encode()).hexdigest()[:12] == digest
                ),
                None,
            )
            if match is None:
                return False
            entries.remove(match)
            save_on_disk_store(store)
            verify = load_on_disk_store()
            remaining = verify.user_entries if target == "user" else verify.memory_entries
            return match not in remaining
        except Exception:
            return False

    @staticmethod
    def upcoming_reminders(source: Any, limit: int = 3) -> list[dict[str, str]] | None:
        """Read useful cron facts for Today without exposing cron controls."""
        try:
            from cron.jobs import list_jobs

            jobs = list_jobs(include_disabled=False)
        except Exception:
            return None
        expected_thread = str(getattr(source, "thread_id", None) or "")
        if expected_thread == "1":
            expected_thread = ""
        result = []
        for job in jobs:
            origin = job.get("origin") or {}
            thread_id = str(origin.get("thread_id") or "")
            if thread_id == "1":
                thread_id = ""
            if (
                str(origin.get("platform") or "").lower() != "telegram"
                or str(origin.get("chat_id") or "") != str(getattr(source, "chat_id", ""))
                or thread_id != expected_thread
            ):
                continue
            result.append({
                "name": str(job.get("name") or "Напоминание"),
                "next_run_at": str(job.get("next_run_at") or ""),
            })
        return result[:limit]


def _runtime_timezone() -> str:
    try:
        from hermes_time import get_timezone

        value = get_timezone()
        return str(getattr(value, "key", value))
    except Exception:
        return "Не настроен"


class CharlineUi:
    """Only the four owner-facing product views."""

    def __init__(
        self,
        projects: ProjectService,
        data: Any = None,
        timezone_loader: Callable[[], str] = _runtime_timezone,
    ):
        self._projects = projects
        self.data = data or HermesUiData()
        self._timezone_loader = timezone_loader
        self._confirmations: OrderedDict[str, tuple[float, tuple[Any, ...]]] = OrderedDict()

    def context(self, source: Any) -> UiContext:
        return UiContext(source=source)

    def _project(self, source: Any, thread_id: str | None = None) -> NativeProject | None:
        wanted = str(thread_id or getattr(source, "thread_id", None) or "")
        return next(
            (item for item in self._projects.list(str(source.chat_id)) if item.thread_id == wanted),
            None,
        )

    def home(self, source: Any) -> dict[str, Any]:
        project = self._project(source)
        if project:
            return {
                "text": (
                    f"Charline · Проект\n\n{project.name}\n\n"
                    "Продолжайте обычным сообщением или голосом. "
                    "Результаты и блокеры появятся в этой теме."
                ),
                "buttons": [],
            }
        return {
            "text": (
                "Charline\n\nНапишите, что нужно, или отправьте голосовое.\n\n"
                "Например: «Что у меня сегодня?», «Запомни задачу купить лампу» "
                "или «Создай и протестируй сайт»."
            ),
            "buttons": [
                [_button("Сегодня", "today"), _button("Проекты", "projects")],
                [_button("Задачи", "personal_tasks"), _button("Настройки", "settings")],
            ],
        }

    def projects(self, source: Any, page: int = 1) -> dict[str, Any]:
        all_projects = self._projects.list(str(source.chat_id))
        page_count = max(1, (len(all_projects) + PROJECT_PAGE_SIZE - 1) // PROJECT_PAGE_SIZE)
        page = min(max(int(page or 1), 1), page_count)
        start = (page - 1) * PROJECT_PAGE_SIZE
        visible = all_projects[start:start + PROJECT_PAGE_SIZE]
        if not visible:
            text = "Проекты\n\nПроектов пока нет. Напишите: «Создай проект …»."
        else:
            lines = ["Проекты", ""]
            lines.extend(f"• {item.name}" for item in visible)
            lines.extend(["", "Откройте нужную тему в Telegram, чтобы продолжить работу."])
            if page_count > 1:
                lines.append(f"Страница {page}/{page_count}")
            text = "\n".join(lines)
        rows = []
        navigation = []
        if page > 1:
            navigation.append(_button("←", f"projects.{page - 1}"))
        if page < page_count:
            navigation.append(_button("→", f"projects.{page + 1}"))
        if navigation:
            rows.append(navigation)
        rows.append([_button("Назад", "home")])
        return {"text": text, "buttons": rows}

    def personal_tasks(self, source: Any) -> dict[str, Any]:
        del source
        tasks = self.data.personal_tasks()
        if tasks is None:
            return {
                "text": "Задачи\n\nНе удалось загрузить задачи.",
                "buttons": [[_button("Обновить", "personal_tasks")], [_button("Назад", "home")]],
            }
        if not tasks:
            text = "Задачи\n\nЗадач пока нет. Напишите: «Запомни задачу …»."
        else:
            text = "\n".join(["Задачи", "", *(f"• {item['title']}" for item in tasks)])
        rows = [
            [_button(f"Выполнено · {item['title']}"[:40], f"personal_task_done.{item['target']}.{item['digest']}")]
            for item in tasks
        ]
        rows.append([_button("Назад", "home")])
        return {"text": text, "buttons": rows}

    def settings(self, source: Any) -> dict[str, Any]:
        del source
        return {
            "text": (
                "Настройки\n\n"
                f"Часовой пояс: {self._timezone_loader()}\n"
                "Доступ: только владелец\n\n"
                "Память, cron, модели и процессы управляются самим Hermes и не "
                "являются настройками ежедневного интерфейса."
            ),
            "buttons": [[_button("Назад", "home")]],
        }

    def _new_confirmation(self, *payload: Any) -> str:
        token = secrets.token_hex(4)
        self._confirmations[token] = (time.monotonic(), payload)
        while len(self._confirmations) > 64:
            self._confirmations.popitem(last=False)
        return token

    def _consume_confirmation(self, token: str, context: UiContext) -> tuple[Any, ...] | None:
        entry = self._confirmations.pop(token, None)
        if entry is None or time.monotonic() - entry[0] > CONFIRM_TTL_SECONDS:
            return None
        payload = entry[1]
        if payload[-3:] != (
            str(context.source.chat_id),
            str(context.source.thread_id or ""),
            str(context.source.user_id or ""),
        ):
            return None
        return payload

    def handle(self, action: str, context: UiContext) -> dict[str, Any]:
        source = context.source
        if action == "home":
            return self.home(source)
        if action == "projects":
            return self.projects(source)
        if action.startswith("projects."):
            try:
                return self.projects(source, int(action.split(".", 1)[1]))
            except ValueError:
                return self.projects(source)
        if action == "personal_tasks":
            return self.personal_tasks(source)
        if action == "settings":
            return self.settings(source)
        if action.startswith("personal_task_done."):
            _, target, digest = action.split(".", 2)
            task = next((
                item for item in self.data.personal_tasks() or []
                if item["target"] == target and item["digest"] == digest
            ), None)
            if task is None:
                return self.personal_tasks(source)
            token = self._new_confirmation(
                "personal_task", target, digest, str(source.chat_id),
                str(source.thread_id or ""), str(source.user_id or ""),
            )
            return {
                "text": f"Отметить задачу выполненной?\n\n{task['title']}",
                "buttons": [[_button("Подтвердить", f"personal_task_confirm.{token}"), _button("Отмена", "personal_tasks")]],
            }
        if action.startswith("personal_task_confirm."):
            payload = self._consume_confirmation(action.rsplit(".", 1)[1], context)
            if payload is None or payload[0] != "personal_task":
                return {"text": "Эта кнопка больше не актуальна.", "buttons": [[_button("К задачам", "personal_tasks")]]}
            done = self.data.delete_memory(str(payload[1]), str(payload[2]))
            card = self.personal_tasks(source)
            card["text"] += "\n\nЗадача выполнена." if done else "\n\nНе удалось подтвердить изменение."
            return card
        return {"text": "Не удалось открыть этот раздел.", "buttons": [[_button("На главную", "home")]]}
