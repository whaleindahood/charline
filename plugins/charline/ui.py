"""Small, reconstructable Telegram views over Hermes-owned state."""

from __future__ import annotations

import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass, replace
from hashlib import sha256
from types import SimpleNamespace
from typing import Any, Callable

from .projects import NativeProject, ProjectService


LIVE_TASK_STATES = {"running", "stalling", "finalizing", "waiting"}
CONFIRM_TTL_SECONDS = 600
PROJECT_PAGE_SIZE = 8
PERSONAL_TASK_PREFIX = "Задача: "


@dataclass(frozen=True)
class UiContext:
    source: Any
    session_key: str


def _button(label: str, action: str) -> dict[str, str]:
    return {"label": label, "action": action}


def _rows(*rows: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    return [row for row in rows if row]


def _count_phrase(count: int, one: str, few: str, many: str) -> str:
    tail = count % 100
    if 11 <= tail <= 14:
        word = many
    elif count % 10 == 1:
        word = one
    elif 2 <= count % 10 <= 4:
        word = few
    else:
        word = many
    return f"{count} {word}"


def _source_with_thread(source: Any, thread_id: str | None) -> Any:
    try:
        return replace(source, thread_id=thread_id)
    except (TypeError, ValueError):
        values = vars(source).copy() if hasattr(source, "__dict__") else {}
        values["thread_id"] = thread_id
        return SimpleNamespace(**values)


def _entity_ref(kind: str, entity_id: str) -> str:
    return sha256(f"{kind}\0{entity_id}".encode()).hexdigest()[:12]


class HermesUiData:
    """Read/write facade over existing Hermes registries; owns no state."""

    @staticmethod
    def tasks(session_key: str) -> list[dict[str, Any]] | None:
        tasks: list[dict[str, Any]] = []
        loaded = 0
        try:
            from tools.async_delegation import list_async_delegations

            delegations = list_async_delegations()
            loaded += 1
            for item in delegations:
                if (
                    str(item.get("session_key") or "") != session_key
                    or item.get("status") not in LIVE_TASK_STATES
                ):
                    continue
                label = " ".join(str(item.get("goal") or "Фоновая задача").split())
                tasks.append({
                    "id": str(item.get("delegation_id") or ""),
                    "kind": "delegation",
                    "label": label[:100],
                    "state": str(item.get("status") or "running"),
                    "elapsed": int(item.get("elapsed_seconds") or 0),
                })
        except Exception:
            pass
        try:
            from tools.process_registry import process_registry

            processes = process_registry.list_sessions(session_key=session_key)
            loaded += 1
            for item in processes:
                if item.get("status") != "running":
                    continue
                label = " ".join(str(item.get("command") or "Фоновый процесс").split())
                tasks.append({
                    "id": str(item.get("session_id") or ""),
                    "kind": "process",
                    "label": label[:100],
                    "state": "running",
                    "elapsed": int(item.get("uptime_seconds") or 0),
                })
        except Exception:
            pass
        return tasks if loaded else None

    @staticmethod
    def pending_count(session_key: str) -> int:
        count = 0
        try:
            from tools.approval import has_blocking_approval

            count += int(bool(has_blocking_approval(session_key)))
        except Exception:
            pass
        try:
            from tools.clarify_gateway import has_pending

            count += int(bool(has_pending(session_key)))
        except Exception:
            pass
        return count

    @staticmethod
    def schedules(source: Any) -> list[dict[str, Any]] | None:
        try:
            from cron.jobs import list_jobs

            jobs = list_jobs(include_disabled=True)
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
            schedule = job.get("schedule") or {}
            result.append({
                "id": str(job.get("id") or ""),
                "name": str(job.get("name") or job.get("id") or "Расписание"),
                "display": str(schedule.get("display") or schedule.get("cron") or ""),
                "enabled": bool(job.get("enabled", True)),
                "next_run_at": str(job.get("next_run_at") or "—"),
                "last_run_at": str(job.get("last_run_at") or "ещё не запускалось"),
                "last_status": str(job.get("last_status") or "—"),
            })
        return result

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

    @staticmethod
    def personal_tasks() -> list[dict[str, str]] | None:
        entries = HermesUiData.memory_entries()
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
    def stop_task(session_key: str, kind: str, task_id: str) -> bool:
        if kind == "process":
            try:
                from tools.process_registry import process_registry

                result = process_registry.kill_process(task_id)
                return bool(result and result.get("status") in {"killed", "already_exited"})
            except Exception:
                return False
        if kind == "delegation":
            try:
                from tools.async_delegation import interrupt_delegation

                return bool(interrupt_delegation(task_id, session_key=session_key))
            except Exception:
                return False
        return False

    def stop_all(self, session_key: str) -> int:
        count = 0
        for task in self.tasks(session_key) or []:
            if self.stop_task(session_key, str(task.get("kind") or ""), str(task.get("id") or "")):
                count += 1
        return count

    @staticmethod
    def mutate_schedule(source: Any, job_id: str, action: str) -> bool:
        try:
            from cron.jobs import get_job, pause_job, remove_job, resume_job, trigger_job

            schedules = HermesUiData.schedules(source)
            if schedules is None:
                return False
            visible = {item["id"] for item in schedules}
            if job_id not in visible:
                return False
            if action == "pause":
                pause_job(job_id, reason="telegram_ui")
                return bool(get_job(job_id) and not get_job(job_id).get("enabled", True))
            if action == "resume":
                resume_job(job_id)
                return bool(get_job(job_id) and get_job(job_id).get("enabled", True))
            if action == "run":
                trigger_job(job_id)
                return get_job(job_id) is not None
            if action == "delete":
                removed = remove_job(job_id)
                return bool(removed and get_job(job_id) is None)
        except Exception:
            return False
        return False

    @staticmethod
    def delete_memory(target: str, digest: str) -> bool:
        try:
            from tools.memory_tool import load_on_disk_store

            item = next(
                (
                    entry for entry in HermesUiData.memory_entries() or []
                    if entry["target"] == target and entry["digest"] == digest
                ),
                None,
            )
            if item is None:
                return False
            result = load_on_disk_store().remove(target, item["content"])
            remaining = HermesUiData.memory_entries() or []
            return bool(
                result.get("success")
                and not any(entry["target"] == target and entry["digest"] == digest for entry in remaining)
            )
        except Exception:
            return False


class CharlineUi:
    """Pure cards plus short-lived mutation confirmations."""

    def __init__(
        self,
        projects: ProjectService,
        data: Any | None = None,
        session_key_builder: Callable[[Any], str] | None = None,
    ):
        self._projects = projects
        self.data = data or HermesUiData()
        self._session_key_builder = session_key_builder or self._build_session_key
        self._confirmations: OrderedDict[str, tuple[float, tuple[Any, ...]]] = OrderedDict()

    @staticmethod
    def _build_session_key(source: Any) -> str:
        from gateway.session import build_session_key

        return build_session_key(source)

    def context(self, source: Any) -> UiContext:
        return UiContext(source=source, session_key=self._session_key_builder(source))

    def _project(self, source: Any, thread_id: str | None = None) -> NativeProject | None:
        wanted = str(thread_id or getattr(source, "thread_id", None) or "")
        return next(
            (item for item in self._projects.list(str(source.chat_id)) if item.thread_id == wanted),
            None,
        )

    def _tasks(self, session_key: str) -> list[dict[str, Any]] | None:
        tasks = self.data.tasks(session_key)
        if tasks is None:
            return None
        return [item for item in tasks if item.get("state") != "foreground"]

    def _schedule(self, source: Any, reference: str) -> dict[str, Any] | None:
        schedules = self.data.schedules(source)
        if schedules is None:
            return None
        return next((
            item for item in schedules
            if str(item.get("id") or "") == reference
            or _entity_ref("schedule", str(item.get("id") or "")) == reference
        ), None)

    def home(self, source: Any) -> dict[str, Any]:
        context = self.context(source)
        project = self._project(source)
        loaded_tasks = self._tasks(context.session_key)
        tasks = loaded_tasks or []
        pending = self.data.pending_count(context.session_key)
        schedules = self.data.schedules(source)
        if project:
            lines = ["Charline · Проект", "", project.name, "", "Продолжайте обычным сообщением или голосом."]
            if tasks:
                lines.extend(["", _count_phrase(len(tasks), "работа выполняется", "работы выполняются", "работ выполняются")])
            if pending:
                lines.append(_count_phrase(pending, "решение ожидает вас", "решения ожидают вас", "решений ожидают вас"))
            if schedules:
                lines.append(_count_phrase(len(schedules), "расписание", "расписания", "расписаний"))
            if loaded_tasks is None or schedules is None:
                lines.append("Часть состояния временно недоступна.")
            return {
                "text": "\n".join(lines),
                "buttons": _rows(
                    [_button(f"В работе · {len(tasks)}", "tasks")] if tasks else [],
                    [_button(f"Расписания · {len(schedules)}", "schedules")] if schedules else [],
                ),
            }
        lines = [
            "Charline", "",
            "Напишите, что нужно, или отправьте голосовое.", "",
            "Например:",
            "• «Что у меня сегодня?»",
            "• «Напомни завтра оплатить счёт»",
            "• «Создай проект Ремонт»",
        ]
        if tasks:
            lines.extend(["", _count_phrase(len(tasks), "работа выполняется", "работы выполняются", "работ выполняются")])
        if pending:
            lines.append(_count_phrase(pending, "решение ожидает вас", "решения ожидают вас", "решений ожидают вас"))
        if loaded_tasks is None:
            lines.append("Не удалось загрузить текущую работу.")
        return {
            "text": "\n".join(lines),
            "buttons": _rows(
                [_button("Проекты", "projects"), _button("Задачи", "personal_tasks")],
                [_button("Расписания", "schedules"), _button("Настройки", "settings")],
            ),
        }

    def today(self, source: Any) -> dict[str, Any]:
        """Backward-compatible alias; a real daily brief is requested conversationally."""
        return self.home(source)

    def projects(self, source: Any, page: int = 1) -> dict[str, Any]:
        all_projects = self._projects.list(str(source.chat_id))
        page_count = max(1, (len(all_projects) + PROJECT_PAGE_SIZE - 1) // PROJECT_PAGE_SIZE)
        page = min(max(int(page or 1), 1), page_count)
        start = (page - 1) * PROJECT_PAGE_SIZE
        projects = all_projects[start:start + PROJECT_PAGE_SIZE]
        if not all_projects:
            text = (
                "Проекты\n\nПроектов пока нет.\n\n"
                "Напишите обычным сообщением: «Создай проект Ремонт»."
            )
        else:
            lines = ["Проекты"]
            for item in projects:
                project_source = _source_with_thread(source, item.thread_id)
                tasks = self._tasks(self._session_key_builder(project_source))
                count = len(tasks or [])
                if tasks is None:
                    status = "данные о работе недоступны"
                elif count:
                    status = _count_phrase(count, "работа выполняется", "работы выполняются", "работ выполняются")
                else:
                    status = "ничего не выполняется"
                lines.extend(["", item.name, status])
            if page_count > 1:
                lines.extend(["", f"Страница {page}/{page_count}"])
            text = "\n".join(lines)
        rows = [
            [_button(f"Статус · {item.name}"[:40], f"project.{item.thread_id}")]
            for item in projects
        ]
        navigation = []
        if page > 1:
            navigation.append(_button("←", f"projects.{page - 1}"))
        if page < page_count:
            navigation.append(_button("→", f"projects.{page + 1}"))
        if navigation:
            rows.append(navigation)
        rows.append([_button("Назад", "home")])
        return {"text": text, "buttons": rows}

    def project_summary(self, source: Any, thread_id: str) -> dict[str, Any]:
        project = self._project(source, thread_id)
        if project is None:
            return {"text": "Этот проект больше не существует.", "buttons": [[_button("К проектам", "projects")]]}
        project_source = _source_with_thread(source, project.thread_id)
        session_key = self._session_key_builder(project_source)
        loaded_tasks = self._tasks(session_key)
        tasks = loaded_tasks or []
        schedules = self.data.schedules(project_source)
        lines = [
            project.name, "",
            f"В работе: {len(tasks)}" if loaded_tasks is not None else "Данные о работе временно недоступны.",
        ]
        if schedules:
            lines.append(f"Расписаний: {len(schedules)}")
        elif schedules is None:
            lines.append("Расписания временно недоступны.")
        inside_project = str(getattr(source, "thread_id", None) or "") == project.thread_id
        if not inside_project:
            lines.extend(["", "Для работы откройте тему проекта в Telegram."])
        project_actions = []
        if tasks:
            project_actions.append(_button("В работе", "tasks" if inside_project else f"project_tasks.{project.thread_id}"))
        if inside_project and schedules:
            project_actions.append(_button("Расписания", "schedules"))
        return {
            "text": "\n".join(lines),
            "buttons": _rows(
                project_actions,
                [_button("Назад", "home" if inside_project else "projects")],
            ),
        }

    def tasks(
        self,
        source: Any,
        *,
        controls: bool = True,
        refresh_action: str = "tasks",
        back_action: str = "home",
    ) -> dict[str, Any]:
        context = self.context(source)
        tasks = self._tasks(context.session_key)
        if tasks is None:
            return {
                "text": "В работе\n\nНе удалось загрузить текущую работу. Попробуйте обновить.",
                "buttons": _rows(
                    [_button("Обновить", refresh_action)],
                    [_button("Назад", back_action)],
                ),
            }
        waiting = self.data.pending_count(context.session_key)
        if not tasks and not waiting:
            text = "В работе\n\nCharline сейчас ничего не выполняет."
        else:
            lines = ["В работе"]
            states = {
                "stalling": "задерживается",
                "finalizing": "завершается",
                "waiting": "ожидает продолжения",
            }
            for item in tasks:
                state = states.get(str(item.get("state") or ""), "выполняется")
                lines.extend(["", str(item.get("label") or "Задача"), f"● {state}"])
            if waiting:
                lines.extend([
                    "", "Ждёт ответа",
                    _count_phrase(waiting, "вопрос", "вопроса", "вопросов"),
                    "Вернитесь к сообщению с вопросом выше, чтобы ответить.",
                ])
            text = "\n".join(lines)
        rows = []
        for item in tasks:
            if controls and item.get("kind") in {"delegation", "process"} and item.get("id"):
                ref = _entity_ref(str(item["kind"]), str(item["id"]))
                rows.append([_button(f"Остановить · {str(item.get('label') or 'задача')[:24]}", f"task_stop.{ref}")])
        if controls and len(rows) > 1:
            rows.append([_button("Остановить всё", "tasks.stop_all")])
        rows.extend([[_button("Обновить", refresh_action)], [_button("Назад", back_action)]])
        return {"text": text, "buttons": rows}

    def personal_tasks(self, source: Any) -> dict[str, Any]:
        del source
        tasks = self.data.personal_tasks()
        if tasks is None:
            return {
                "text": "Задачи\n\nНе удалось загрузить личные задачи. Попробуйте обновить.",
                "buttons": [[_button("Обновить", "personal_tasks")], [_button("Назад", "home")]],
            }
        if not tasks:
            text = (
                "Задачи\n\nЗадач пока нет.\n\n"
                "Напишите обычным сообщением, например: «Запомни, мне нужно сделать лабораторную»."
            )
        else:
            lines = ["Задачи"]
            for task in tasks:
                lines.extend(["", f"• {task['title']}"])
            text = "\n".join(lines)
        rows = [
            [_button(
                f"Выполнено · {task['title']}"[:40],
                f"personal_task_done.{task['target']}.{task['digest']}",
            )]
            for task in tasks
        ]
        rows.append([_button("Назад", "home")])
        return {"text": text, "buttons": rows}

    def schedules(self, source: Any, *, back_action: str = "home") -> dict[str, Any]:
        jobs = self.data.schedules(source)
        if jobs is None:
            return {
                "text": "Расписания\n\nНе удалось загрузить расписания. Попробуйте обновить.",
                "buttons": _rows(
                    [_button("Обновить", "schedules")],
                    [_button("Назад", back_action)],
                ),
            }
        if not jobs:
            text = (
                "Расписания\n\nРасписаний пока нет.\n\n"
                "Можно просто написать:\n«Каждый будний день в 9 утра присылай мне план дня»."
            )
        else:
            lines = ["Расписания"]
            for job in jobs:
                status = "активно" if job.get("enabled") else "на паузе"
                lines.extend([
                    "", str(job.get("name") or "Расписание"),
                    str(job.get("display") or ""),
                    f"Следующий запуск: {job.get('next_run_at') or '—'}",
                    f"● {status}",
                ])
            text = "\n".join(lines)
        rows = [
            [_button(str(job.get("name") or "Расписание")[:30], f"schedule.{_entity_ref('schedule', str(job['id']))}")]
            for job in jobs if job.get("id")
        ]
        rows.append([_button("Назад", back_action)])
        return {"text": text, "buttons": rows}

    def schedule_detail(self, source: Any, job_id: str) -> dict[str, Any]:
        if self.data.schedules(source) is None:
            return {
                "text": "Расписания\n\nНе удалось загрузить расписания. Попробуйте обновить.",
                "buttons": [[_button("К расписаниям", "schedules")]],
            }
        job = self._schedule(source, job_id)
        if job is None:
            return {"text": "Это расписание больше не существует.", "buttons": [[_button("К расписаниям", "schedules")]]}
        last_status = {
            "ok": "успешно",
            "success": "успешно",
            "error": "ошибка",
            "running": "выполняется",
        }.get(str(job.get("last_status") or "").lower(), str(job.get("last_status") or "—"))
        lines = [
            str(job.get("name") or "Расписание"), "",
            f"Когда: {job.get('display') or 'не указано'}",
            f"Следующий запуск: {job.get('next_run_at') or '—'}",
            f"Последний запуск: {job.get('last_run_at') or 'ещё не запускалось'} · {last_status}",
        ]
        ref = _entity_ref("schedule", job_id)
        toggle = _button("Пауза", f"schedule_pause.{ref}") if job.get("enabled") else _button("Возобновить", f"schedule_resume.{ref}")
        return {
            "text": "\n".join(lines),
            "buttons": _rows(
                [_button("Запустить сейчас", f"schedule_run.{ref}"), toggle],
                [_button("Удалить", f"schedule_delete.{ref}")],
                [_button("Назад", "schedules")],
            ),
        }

    def settings(self, source: Any) -> dict[str, Any]:
        del source
        return {
            "text": (
                "Данные Charline\n\n"
                "Здесь можно проверить сохранённую память и расписания.\n"
                "Внешние действия всегда требуют подтверждения."
            ),
            "buttons": _rows(
                [_button("Память", "memory")],
                [_button("Расписания", "settings.schedules")],
                [_button("Назад", "home")],
            ),
        }

    def memory(self, source: Any) -> dict[str, Any]:
        del source
        entries = self.data.memory_entries()
        if entries is None:
            return {
                "text": "Память\n\nНе удалось загрузить память. Попробуйте обновить.",
                "buttons": [[_button("Обновить", "memory")], [_button("Назад", "settings")]],
            }
        lines = ["Память"]
        if not entries:
            lines.extend(["", "Долговременная память пока пуста."])
        else:
            for entry in entries:
                lines.extend(["", f"• {entry['content']}"])
        rows = [
            [_button(f"Удалить · {entry['content'][:22]}", f"memory_delete.{entry['target']}.{entry['digest']}")]
            for entry in entries
        ]
        rows.append([_button("Назад", "settings")])
        return {"text": "\n".join(lines), "buttons": rows}

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
        if action == "today":
            return self.today(source)
        if action == "projects":
            return self.projects(source)
        if action.startswith("projects."):
            try:
                return self.projects(source, int(action.split(".", 1)[1]))
            except ValueError:
                return self.projects(source)
        if action == "tasks":
            return self.tasks(source)
        if action == "personal_tasks":
            return self.personal_tasks(source)
        if action == "schedules":
            return self.schedules(source)
        if action == "settings.schedules":
            return self.schedules(source, back_action="settings")
        if action == "settings":
            return self.settings(source)
        if action == "memory":
            return self.memory(source)
        if action.startswith("project.") or action.startswith("summary."):
            return self.project_summary(source, action.split(".", 1)[1])
        if action.startswith("project_tasks."):
            thread_id = action.split(".", 1)[1]
            if self._project(source, thread_id) is None:
                return self.project_summary(source, thread_id)
            return self.tasks(
                _source_with_thread(source, thread_id),
                controls=False,
                refresh_action=f"project_tasks.{thread_id}",
                back_action=f"summary.{thread_id}",
            )
        if action.startswith("personal_task_done."):
            _, target, digest = action.split(".", 2)
            task = next((
                item for item in self.data.personal_tasks() or []
                if item["target"] == target and item["digest"] == digest
            ), None)
            if task is None:
                card = self.personal_tasks(source)
                card["text"] += "\n\nЗадача уже выполнена или удалена."
                return card
            token = self._new_confirmation(
                "personal_task", target, digest, str(source.chat_id),
                str(source.thread_id or ""), str(source.user_id or ""),
            )
            return {
                "text": f"Отметить задачу выполненной?\n\n{task['title']}",
                "buttons": [
                    [_button("Выполнено", f"personal_task_confirm.{token}")],
                    [_button("Отмена", "personal_tasks")],
                ],
            }
        if action.startswith("personal_task_confirm."):
            payload = self._consume_confirmation(action.rsplit(".", 1)[1], context)
            if payload is None or payload[0] != "personal_task":
                return {"text": "Эта кнопка больше не актуальна.", "buttons": [[_button("К задачам", "personal_tasks")]]}
            done = self.data.delete_memory(str(payload[1]), str(payload[2]))
            card = self.personal_tasks(source)
            card["text"] += "\n\nЗадача выполнена." if done else "\n\nНе удалось подтвердить выполнение."
            return card
        if action.startswith("schedule."):
            reference = action.split(".", 1)[1]
            job = self._schedule(source, reference)
            return self.schedule_detail(source, str(job.get("id"))) if job else self.schedule_detail(source, reference)
        if action.startswith("task_stop."):
            parts = action.split(".", 2)
            if len(parts) == 3:
                _, kind, task_id = parts
                task = next((
                    item for item in self.data.tasks(context.session_key) or []
                    if item.get("kind") == kind and str(item.get("id") or "") == task_id
                ), None)
            else:
                reference = parts[1]
                task = next((
                    item for item in self.data.tasks(context.session_key) or []
                    if item.get("kind") in {"delegation", "process"}
                    and _entity_ref(str(item["kind"]), str(item.get("id") or "")) == reference
                ), None)
            if task is None:
                card = self.tasks(source)
                card["text"] += "\n\nЗадача уже завершена или больше не доступна."
                return card
            token = self._new_confirmation(
                "task", context.session_key, str(task["kind"]), str(task["id"]),
                str(source.chat_id), str(source.thread_id or ""), str(source.user_id or ""),
            )
            return {
                "text": f"Остановить работу «{str(task.get('label') or 'Задача')}»?",
                "buttons": [
                    [_button("Остановить", f"task_confirm.{token}")],
                    [_button("Отмена", "tasks")],
                ],
            }
        if action.startswith("task_confirm."):
            payload = self._consume_confirmation(action.rsplit(".", 1)[1], context)
            if payload is None or payload[0] != "task":
                return {"text": "Эта кнопка больше не актуальна.", "buttons": [[_button("К работе", "tasks")]]}
            done = self.data.stop_task(str(payload[1]), str(payload[2]), str(payload[3]))
            card = self.tasks(source)
            card["text"] += "\n\nОстановка запрошена." if done else "\n\nЗадача уже завершена или не найдена."
            return card
        if action == "tasks.stop_all":
            count = len([
                item for item in self.data.tasks(context.session_key) or []
                if item.get("kind") in {"delegation", "process"}
            ])
            if not count:
                return self.tasks(source)
            token = self._new_confirmation(
                "tasks", context.session_key, str(source.chat_id),
                str(source.thread_id or ""), str(source.user_id or ""),
            )
            return {
                "text": f"Остановить всю текущую работу ({count})?",
                "buttons": [[_button("Остановить все", f"tasks.confirm.{token}")], [_button("Отмена", "tasks")]],
            }
        if action.startswith("tasks.confirm."):
            payload = self._consume_confirmation(action.rsplit(".", 1)[1], context)
            if payload is None or payload[0] != "tasks":
                return {"text": "Эта кнопка больше не актуальна.", "buttons": [[_button("К работе", "tasks")]]}
            count = self.data.stop_all(str(payload[1]))
            card = self.tasks(source)
            card["text"] += f"\n\nОстановлено: {count}."
            return card
        schedule_actions = {
            "pause": ("Приостановить", "Расписание приостановлено."),
            "resume": ("Возобновить", "Расписание возобновлено."),
            "run": ("Запустить сейчас", "Запуск поставлен в очередь."),
            "delete": ("Удалить", "Расписание удалено."),
        }
        for verb, (button_label, _) in schedule_actions.items():
            prefix = f"schedule_{verb}."
            if action.startswith(prefix):
                reference = action[len(prefix):]
                job = self._schedule(source, reference)
                if job is None:
                    return self.schedule_detail(source, reference)
                job_id = str(job["id"])
                token = self._new_confirmation(
                    "schedule", verb, job_id, str(source.chat_id),
                    str(source.thread_id or ""), str(source.user_id or ""),
                )
                name = str(job.get("name") or "это расписание")
                question = (
                    f"Запустить расписание «{name}» сейчас?"
                    if verb == "run"
                    else f"{button_label} расписание «{name}»?"
                )
                return {
                    "text": question,
                    "buttons": [
                        [_button(button_label, f"schedule_confirm.{token}")],
                        [_button("Отмена", f"schedule.{_entity_ref('schedule', job_id)}")],
                    ],
                }
        if action.startswith("schedule_confirm."):
            payload = self._consume_confirmation(action.rsplit(".", 1)[1], context)
            if payload is None or payload[0] != "schedule":
                return {"text": "Эта кнопка больше не актуальна.", "buttons": [[_button("К расписаниям", "schedules")]]}
            verb, job_id = str(payload[1]), str(payload[2])
            if verb not in schedule_actions:
                return {"text": "Эта кнопка больше не актуальна.", "buttons": [[_button("К расписаниям", "schedules")]]}
            done = self.data.mutate_schedule(source, job_id, verb)
            card = self.schedules(source) if verb == "delete" else self.schedule_detail(source, job_id)
            if done:
                card["text"] += f"\n\n{schedule_actions[verb][1]}"
            else:
                card["text"] += "\n\nНе удалось подтвердить действие."
            return card
        if action.startswith("memory_delete."):
            _, target, digest = action.split(".", 2)
            entries = self.data.memory_entries()
            if entries is None:
                return self.memory(source)
            entry = next((
                item for item in entries
                if item["target"] == target and item["digest"] == digest
            ), None)
            if entry is None:
                return {"text": "Эта запись памяти больше не существует.", "buttons": [[_button("К памяти", "memory")]]}
            token = self._new_confirmation(
                "memory", target, digest, str(source.chat_id),
                str(source.thread_id or ""), str(source.user_id or ""),
            )
            return {
                "text": f"Удалить из долговременной памяти?\n\n{entry['content']}",
                "buttons": [[_button("Удалить", f"memory_confirm.{token}")], [_button("Отмена", "memory")]],
            }
        if action.startswith("memory_confirm."):
            payload = self._consume_confirmation(action.rsplit(".", 1)[1], context)
            if payload is None or payload[0] != "memory":
                return {"text": "Эта кнопка больше не актуальна.", "buttons": [[_button("К памяти", "memory")]]}
            done = self.data.delete_memory(str(payload[1]), str(payload[2]))
            card = self.memory(source)
            card["text"] += "\n\nЗапись удалена." if done else "\n\nНе удалось подтвердить удаление."
            return card
        return {"text": "Не удалось открыть этот раздел.", "buttons": [[_button("На главную", "home")]]}
