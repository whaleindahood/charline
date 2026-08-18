"""Small, reconstructable Telegram views over Hermes-owned state."""

from __future__ import annotations

import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Any, Callable

from .projects import NativeProject, ProjectService


LIVE_TASK_STATES = {"running", "stalling", "finalizing", "waiting"}
CONFIRM_TTL_SECONDS = 600
PROJECT_PAGE_SIZE = 8


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


class HermesUiData:
    """Read/write facade over existing Hermes registries; owns no state."""

    @staticmethod
    def tasks(session_key: str) -> list[dict[str, Any]]:
        tasks: list[dict[str, Any]] = []
        try:
            from tools.async_delegation import list_async_delegations

            for item in list_async_delegations():
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

            for item in process_registry.list_sessions(session_key=session_key):
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
        return tasks

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
    def schedules(source: Any) -> list[dict[str, Any]]:
        try:
            from cron.jobs import list_jobs

            jobs = list_jobs(include_disabled=True)
        except Exception:
            return []
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
    def memory_entries() -> list[dict[str, str]]:
        try:
            from hashlib import sha256
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
            return []

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
        for task in self.tasks(session_key):
            if self.stop_task(session_key, str(task.get("kind") or ""), str(task.get("id") or "")):
                count += 1
        return count

    @staticmethod
    def mutate_schedule(source: Any, job_id: str, action: str) -> bool:
        try:
            from cron.jobs import get_job, pause_job, remove_job, resume_job, trigger_job

            visible = {item["id"] for item in HermesUiData.schedules(source)}
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
                    entry for entry in HermesUiData.memory_entries()
                    if entry["target"] == target and entry["digest"] == digest
                ),
                None,
            )
            if item is None:
                return False
            result = load_on_disk_store().remove(target, item["content"])
            remaining = HermesUiData.memory_entries()
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

    def home(self, source: Any) -> dict[str, Any]:
        context = self.context(source)
        project = self._project(source)
        tasks = [item for item in self.data.tasks(context.session_key) if item.get("state") != "foreground"]
        pending = self.data.pending_count(context.session_key)
        if project:
            lines = ["Charline · Проект", "", project.name]
            if tasks:
                lines.extend(["", _count_phrase(len(tasks), "задача выполняется", "задачи выполняются", "задач выполняются")])
            if pending:
                lines.append(_count_phrase(pending, "решение ожидает вас", "решения ожидают вас", "решений ожидают вас"))
            return {
                "text": "\n".join(lines),
                "buttons": _rows(
                    [_button("Сводка", f"summary.{project.thread_id}"), _button("Задачи", "tasks")],
                    [_button("Расписания", "schedules"), _button("Управление", f"manage.{project.thread_id}")],
                ),
            }
        lines = ["Charline"]
        if tasks:
            lines.extend(["", _count_phrase(len(tasks), "активная задача", "активные задачи", "активных задач")])
        if pending:
            lines.append(_count_phrase(pending, "решение ожидает вас", "решения ожидают вас", "решений ожидают вас"))
        return {
            "text": "\n".join(lines),
            "buttons": _rows(
                [_button("Сегодня", "today")],
                [_button("Проекты", "projects"), _button("Задачи", "tasks")],
                [_button("Расписания", "schedules"), _button("Настройки", "settings")],
            ),
        }

    def today(self, source: Any) -> dict[str, Any]:
        context = self.context(source)
        tasks = [item for item in self.data.tasks(context.session_key) if item.get("state") != "foreground"]
        pending = self.data.pending_count(context.session_key)
        schedules = self.data.schedules(source)
        lines = ["Сегодня", ""]
        if tasks:
            lines.append(_count_phrase(len(tasks), "задача выполняется", "задачи выполняются", "задач выполняются"))
        if pending:
            lines.append(_count_phrase(pending, "задача ждёт вашего решения", "задачи ждут вашего решения", "задач ждут вашего решения"))
        if schedules:
            lines.append(f"Следующее расписание: {schedules[0].get('next_run_at') or '—'}")
        if not tasks and not pending and not schedules:
            lines.append("На сегодня ничего срочного.")
        buttons = []
        if tasks or pending:
            buttons.append(_button(f"Задачи · {len(tasks) + pending}", "tasks"))
        if schedules:
            buttons.append(_button("Расписания", "schedules"))
        return {"text": "\n".join(lines), "buttons": _rows(buttons, [_button("Назад", "home")])}

    def projects(self, source: Any, page: int = 1) -> dict[str, Any]:
        all_projects = self._projects.list(str(source.chat_id))
        page_count = max(1, (len(all_projects) + PROJECT_PAGE_SIZE - 1) // PROJECT_PAGE_SIZE)
        page = min(max(int(page or 1), 1), page_count)
        start = (page - 1) * PROJECT_PAGE_SIZE
        projects = all_projects[start:start + PROJECT_PAGE_SIZE]
        if not all_projects:
            text = (
                "Проекты\n\nПроектов пока нет.\n\n"
                "Можете создать проект здесь или просто написать мне, над чем хотите работать."
            )
        else:
            lines = ["Проекты"]
            for item in projects:
                project_source = _source_with_thread(source, item.thread_id)
                count = len([
                    task for task in self.data.tasks(self._session_key_builder(project_source))
                    if task.get("state") != "foreground"
                ])
                status = _count_phrase(count, "активная задача", "активные задачи", "активных задач") if count else "нет активных задач"
                lines.extend(["", item.name, status])
            if page_count > 1:
                lines.extend(["", f"Страница {page}/{page_count}"])
            text = "\n".join(lines)
        rows = [
            [_button(item.name, f"project.{item.thread_id}")]
            for item in projects
        ]
        navigation = []
        if page > 1:
            navigation.append(_button("←", f"projects.{page - 1}"))
        if page < page_count:
            navigation.append(_button("→", f"projects.{page + 1}"))
        if navigation:
            rows.append(navigation)
        rows.extend([[_button("＋ Новый проект", "new_project")], [_button("Назад", "home")]])
        return {"text": text, "buttons": rows}

    def project_summary(self, source: Any, thread_id: str) -> dict[str, Any]:
        project = self._project(source, thread_id)
        if project is None:
            return {"text": "Этот проект больше не существует.", "buttons": [[_button("К проектам", "projects")]]}
        project_source = _source_with_thread(source, project.thread_id)
        session_key = self._session_key_builder(project_source)
        tasks = [item for item in self.data.tasks(session_key) if item.get("state") != "foreground"]
        schedules = self.data.schedules(project_source)
        lines = [project.name, "", f"Активных задач: {len(tasks)}"]
        if schedules:
            lines.append(f"Расписаний: {len(schedules)}")
        inside_project = str(getattr(source, "thread_id", None) or "") == project.thread_id
        project_actions = [_button("Задачи", "tasks" if inside_project else f"project_tasks.{project.thread_id}")]
        if inside_project and schedules:
            project_actions.append(_button("Расписания", "schedules"))
        return {
            "text": "\n".join(lines),
            "buttons": _rows(
                project_actions,
                [_button("Назад", "home" if inside_project else "projects")],
            ),
        }

    def project_management(self, source: Any, thread_id: str) -> dict[str, Any]:
        project = self._project(source, thread_id)
        if project is None:
            return self.project_summary(source, thread_id)
        return {
            "text": (
                f"Управление проектом\n\n{project.name}\n\n"
                "Переименование и закрытие темы выполняются средствами Telegram. "
                "История Hermes при этом не удаляется."
            ),
            "buttons": [[_button("Назад", f"summary.{thread_id}")]],
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
        tasks = [item for item in self.data.tasks(context.session_key) if item.get("state") != "foreground"]
        waiting = self.data.pending_count(context.session_key)
        tasks.extend(
            {"id": f"waiting-{index}", "label": "Требуется ваше решение", "state": "waiting"}
            for index in range(waiting)
        )
        if not tasks:
            text = "Задачи\n\nАктивных задач сейчас нет."
        else:
            lines = ["Задачи"]
            for item in tasks:
                state = "ожидает вас" if item.get("state") == "waiting" else "выполняется"
                lines.extend(["", str(item.get("label") or "Задача"), f"● {state}"])
            text = "\n".join(lines)
        rows = []
        for item in tasks:
            if controls and item.get("kind") in {"delegation", "process"} and item.get("id"):
                rows.append([_button(f"Остановить · {str(item.get('label') or 'задача')[:24]}", f"task_stop.{item['kind']}.{item['id']}")])
        if controls and len(rows) > 1:
            rows.append([_button("Остановить всё", "tasks.stop_all")])
        rows.extend([[_button("Обновить", refresh_action)], [_button("Назад", back_action)]])
        return {"text": text, "buttons": rows}

    def schedules(self, source: Any) -> dict[str, Any]:
        jobs = self.data.schedules(source)
        if not jobs:
            text = (
                "Расписания\n\nРасписаний пока нет.\n\n"
                "Можно просто написать:\n«Каждый будний день в 9 утра присылай мне план дня»."
            )
        else:
            lines = ["Расписания"]
            for job in jobs:
                status = "активно" if job.get("enabled") else "на паузе"
                lines.extend(["", str(job.get("name") or "Расписание"), str(job.get("display") or ""), f"● {status}"])
            text = "\n".join(lines)
        rows = [[_button(str(job.get("name") or "Подробнее")[:30], f"schedule.{job['id']}")] for job in jobs if job.get("id")]
        rows.extend([[_button("＋ Создать", "schedule_new")], [_button("Назад", "home")]])
        return {"text": text, "buttons": rows}

    def schedule_detail(self, source: Any, job_id: str) -> dict[str, Any]:
        job = next((item for item in self.data.schedules(source) if item.get("id") == job_id), None)
        if job is None:
            return {"text": "Это расписание больше не существует.", "buttons": [[_button("К расписаниям", "schedules")]]}
        lines = [
            str(job.get("name") or "Расписание"), "",
            f"Следующий запуск: {job.get('next_run_at') or '—'}",
            f"Последний запуск: {job.get('last_run_at') or 'ещё не запускалось'} · {job.get('last_status') or '—'}",
        ]
        toggle = _button("Пауза", f"schedule_pause.{job_id}") if job.get("enabled") else _button("Возобновить", f"schedule_resume.{job_id}")
        return {
            "text": "\n".join(lines),
            "buttons": _rows(
                [_button("Запустить сейчас", f"schedule_run.{job_id}"), toggle],
                [_button("Удалить", f"schedule_delete.{job_id}")],
                [_button("Назад", "schedules")],
            ),
        }

    def settings(self, source: Any) -> dict[str, Any]:
        del source
        return {
            "text": "Настройки",
            "buttons": _rows(
                [_button("Память", "memory")],
                [_button("Расширенное", "advanced")],
                [_button("Назад", "home")],
            ),
        }

    def memory(self, source: Any) -> dict[str, Any]:
        del source
        entries = self.data.memory_entries()
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
        if action == "schedules":
            return self.schedules(source)
        if action == "settings":
            return self.settings(source)
        if action == "memory":
            return self.memory(source)
        if action == "advanced":
            return {
                "text": "Расширенное\n\nКоманды: /commands\nСостояние: /status\nМодель: /model",
                "buttons": [[_button("Назад", "settings")]],
            }
        if action == "new_project":
            return {
                "text": "Новый проект\n\nКак назвать проект?\n\nНапишите: /projects new <название>\nили просто скажите: «Создай проект …».",
                "buttons": [[_button("Назад", "projects")]],
            }
        if action == "schedule_new":
            return {
                "text": "Новое расписание\n\nПросто напишите, что и когда нужно делать.\nНапример: «Каждый будний день в 9 утра присылай мне план дня».",
                "buttons": [[_button("Назад", "schedules")]],
            }
        if action.startswith("project.") or action.startswith("summary."):
            return self.project_summary(source, action.split(".", 1)[1])
        if action.startswith("manage."):
            return self.project_management(source, action.split(".", 1)[1])
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
        if action.startswith("schedule."):
            return self.schedule_detail(source, action.split(".", 1)[1])
        if action.startswith("task_stop."):
            _, kind, task_id = action.split(".", 2)
            done = self.data.stop_task(context.session_key, kind, task_id)
            card = self.tasks(source)
            card["text"] += "\n\nОстановка запрошена." if done else "\n\nНе удалось остановить задачу."
            return card
        if action == "tasks.stop_all":
            count = len([
                item for item in self.data.tasks(context.session_key)
                if item.get("kind") in {"delegation", "process"}
            ])
            if not count:
                return self.tasks(source)
            token = self._new_confirmation(
                "tasks", context.session_key, str(source.chat_id),
                str(source.thread_id or ""), str(source.user_id or ""),
            )
            return {
                "text": f"Остановить все {count} задач?",
                "buttons": [[_button("Остановить все", f"tasks.confirm.{token}")], [_button("Отмена", "tasks")]],
            }
        if action.startswith("tasks.confirm."):
            payload = self._consume_confirmation(action.rsplit(".", 1)[1], context)
            if payload is None or payload[0] != "tasks":
                return {"text": "Эта кнопка больше не актуальна.", "buttons": [[_button("К задачам", "tasks")]]}
            count = self.data.stop_all(str(payload[1]))
            card = self.tasks(source)
            card["text"] += f"\n\nОстановлено задач: {count}."
            return card
        for verb in ("pause", "resume", "run"):
            prefix = f"schedule_{verb}."
            if action.startswith(prefix):
                job_id = action[len(prefix):]
                done = self.data.mutate_schedule(source, job_id, verb)
                card = self.schedule_detail(source, job_id)
                if not done:
                    card["text"] += "\n\nНе удалось выполнить действие."
                return card
        if action.startswith("schedule_delete."):
            job_id = action.split(".", 1)[1]
            if not any(item.get("id") == job_id for item in self.data.schedules(source)):
                return self.schedule_detail(source, job_id)
            token = self._new_confirmation(
                "schedule", job_id, str(source.chat_id),
                str(source.thread_id or ""), str(source.user_id or ""),
            )
            return {
                "text": "Удалить это расписание? История сессий не удаляется.",
                "buttons": [[_button("Удалить", f"schedule_confirm.{token}")], [_button("Отмена", f"schedule.{job_id}")]],
            }
        if action.startswith("schedule_confirm."):
            payload = self._consume_confirmation(action.rsplit(".", 1)[1], context)
            if payload is None or payload[0] != "schedule":
                return {"text": "Эта кнопка больше не актуальна.", "buttons": [[_button("К расписаниям", "schedules")]]}
            done = self.data.mutate_schedule(source, str(payload[1]), "delete")
            card = self.schedules(source)
            card["text"] += "\n\nРасписание удалено." if done else "\n\nНе удалось подтвердить удаление."
            return card
        if action.startswith("memory_delete."):
            _, target, digest = action.split(".", 2)
            if not any(item["target"] == target and item["digest"] == digest for item in self.data.memory_entries()):
                return {"text": "Эта запись памяти больше не существует.", "buttons": [[_button("К памяти", "memory")]]}
            token = self._new_confirmation(
                "memory", target, digest, str(source.chat_id),
                str(source.thread_id or ""), str(source.user_id or ""),
            )
            return {
                "text": "Удалить эту запись из долговременной памяти?",
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
