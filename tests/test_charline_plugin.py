from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from plugins.charline import CharlinePlugin, register
from plugins.charline.ui import CharlineUi
from plugins.charline.projects import (
    ProjectNameError,
    ProjectService,
    list_native_projects,
    normalize_project_name,
)


def _source(*, thread_id=None, chat_type="dm"):
    return SimpleNamespace(
        platform=SimpleNamespace(value="telegram"),
        chat_id="123",
        thread_id=thread_id,
        user_id="42",
        chat_type=chat_type,
    )


class FakeUiData:
    def __init__(self):
        self.tasks_by_session = {}
        self.schedules_by_thread = {}
        self.memories = []
        self.pending_by_session = {}
        self.calls = []
        self.tasks_available = True
        self.schedules_available = True
        self.memory_available = True

    def tasks(self, session_key):
        if not self.tasks_available:
            return None
        return list(self.tasks_by_session.get(session_key, []))

    def schedules(self, source):
        if not self.schedules_available:
            return None
        return list(self.schedules_by_thread.get(str(source.thread_id or ""), []))

    def memory_entries(self):
        if not self.memory_available:
            return None
        return list(self.memories)

    def personal_tasks(self):
        if not self.memory_available:
            return None
        return [
            {
                "title": item["content"][len("Задача: "):],
                "target": item["target"],
                "digest": item["digest"],
            }
            for item in self.memories
            if item.get("content", "").startswith("Задача: ")
        ]

    def pending_count(self, session_key):
        return int(self.pending_by_session.get(session_key, 0))

    def stop_task(self, session_key, kind, task_id):
        self.calls.append(("stop_task", session_key, kind, task_id))
        before = len(self.tasks_by_session.get(session_key, []))
        self.tasks_by_session[session_key] = [
            item for item in self.tasks_by_session.get(session_key, [])
            if item.get("id") != task_id
        ]
        return len(self.tasks_by_session[session_key]) < before

    def stop_all(self, session_key):
        self.calls.append(("stop_all", session_key))
        count = len(self.tasks_by_session.get(session_key, []))
        self.tasks_by_session[session_key] = []
        return count

    def mutate_schedule(self, source, job_id, action):
        self.calls.append(("schedule", str(source.thread_id or ""), job_id, action))
        jobs = self.schedules_by_thread.get(str(source.thread_id or ""), [])
        target = next((item for item in jobs if item.get("id") == job_id), None)
        if target is None:
            return False
        if action == "delete":
            jobs.remove(target)
        elif action == "pause":
            target["enabled"] = False
        elif action == "resume":
            target["enabled"] = True
        return True

    def delete_memory(self, target, digest):
        self.calls.append(("memory", target, digest))
        before = len(self.memories)
        self.memories = [
            item for item in self.memories
            if not (item.get("target") == target and item.get("digest") == digest)
        ]
        return len(self.memories) < before


def test_project_name_normalization() -> None:
    assert normalize_project_name("  Project   Alpha  ") == "Project Alpha"
    with pytest.raises(ProjectNameError):
        normalize_project_name("bad\nname")
    with pytest.raises(ProjectNameError):
        normalize_project_name("x" * 129)


def test_project_index_is_a_read_only_view_of_native_dm_topics() -> None:
    config = {
        "platforms": {"telegram": {"extra": {"dm_topics": [
            {"chat_id": 123, "topics": [
                {"name": "Alpha", "thread_id": 11},
                {"name": "Pending", "thread_id": "auto"},
            ]},
            {"chat_id": 999, "topics": [{"name": "Foreign", "thread_id": 99}]},
        ]}}}
    }
    assert [(p.name, p.thread_id) for p in list_native_projects(config, "123")] == [
        ("Alpha", "11")
    ]


def test_project_start_uses_native_topic_task_action() -> None:
    config = {"platforms": {"telegram": {"extra": {"dm_topics": []}}}}

    async def start(_platform, chat_id, name, task, owner_user_id, request_id):
        config["platforms"]["telegram"]["extra"]["dm_topics"] = [
            {"chat_id": chat_id, "topics": [{"name": name, "thread_id": 77}]}
        ]
        return {
            "ok": True, "thread_id": "77", "request_id": request_id,
            "task": task, "owner_user_id": owner_user_id,
        }

    actions = SimpleNamespace(start_private_topic_task=AsyncMock(side_effect=start))
    service = ProjectService(actions, config_loader=lambda: config)
    result = asyncio.run(service.start(
        "123", "42", " Project  Alpha ", "Build and test the website"
    ))

    assert result.thread_id == "77"
    call = actions.start_private_topic_task.await_args
    assert call.args[:4] == (
        "telegram", "123", "Project Alpha", "Build and test the website"
    )
    assert call.kwargs["owner_user_id"] == "42"
    assert call.kwargs["request_id"].startswith("charline-")


def test_plugin_registers_commands_tool_and_hook() -> None:
    ctx = MagicMock()
    ctx.platform_actions = MagicMock()
    register(ctx)
    assert {call.kwargs["name"] for call in ctx.register_command.call_args_list} == {
        "charline", "charline-tasks", "projects", "schedules", "settings", "today"
    }
    ctx.register_tool.assert_called_once()
    assert ctx.register_tool.call_args.kwargs["name"] == "charline_projects"
    assert ctx.register_tool.call_args.kwargs["is_async"] is True
    assert [call.args[0] for call in ctx.register_hook.call_args_list] == [
        "pre_gateway_dispatch", "gateway_platform_event"
    ]


def test_today_command_starts_a_normal_hermes_turn_in_main() -> None:
    actions = SimpleNamespace(
        dispatch_agent_turn=AsyncMock(return_value={"ok": True}),
        ensure_private_topic=AsyncMock(),
    )
    plugin = CharlinePlugin(
        SimpleNamespace(platform_actions=actions),
        config_loader=lambda: {},
    )
    plugin.capture_request(
        SimpleNamespace(source=_source(), text="/today"), MagicMock()
    )

    assert asyncio.run(plugin.today_command("")) is None
    kwargs = actions.dispatch_agent_turn.await_args.kwargs
    assert kwargs["chat_id"] == "123"
    assert kwargs["owner_user_id"] == "42"
    assert kwargs["thread_id"] == ""
    assert "календар" in kwargs["prompt"].lower()
    assert "личные задачи" in kwargs["prompt"].lower()


def test_root_and_project_context_are_never_rewritten_by_hook() -> None:
    plugin = CharlinePlugin(SimpleNamespace(platform_actions=MagicMock()))
    gateway = MagicMock()
    root = SimpleNamespace(source=_source(thread_id=None), text="hello")
    project = SimpleNamespace(source=_source(thread_id="77"), text="hello")
    assert plugin.capture_request(root, gateway=gateway, session_store=MagicMock()) is None
    assert plugin.current_request().source.thread_id is None
    assert plugin.capture_request(project, gateway=gateway, session_store=MagicMock()) is None
    assert plugin.current_request().source.thread_id == "77"
    assert root.text == "hello"
    assert project.text == "hello"


def test_projects_new_command_and_tool_share_project_service() -> None:
    config = {"platforms": {"telegram": {"extra": {"dm_topics": []}}}}

    async def ensure(_platform, chat_id, name):
        config["platforms"]["telegram"]["extra"]["dm_topics"] = [
            {"chat_id": chat_id, "topics": [{"name": name, "thread_id": 88}]}
        ]
        return {"ok": True, "thread_id": "88"}

    async def start(_platform, chat_id, name, task, owner_user_id, request_id):
        config["platforms"]["telegram"]["extra"]["dm_topics"] = [
            {"chat_id": chat_id, "topics": [{"name": name, "thread_id": 99}]}
        ]
        return {"ok": True, "thread_id": "99", "request_id": request_id}

    actions = SimpleNamespace(
        ensure_private_topic=AsyncMock(side_effect=ensure),
        start_private_topic_task=AsyncMock(side_effect=start),
    )
    plugin = CharlinePlugin(
        SimpleNamespace(platform_actions=actions), config_loader=lambda: config
    )
    plugin.capture_request(
        SimpleNamespace(source=_source(), text="/projects new Alpha"),
        gateway=MagicMock(),
        session_store=MagicMock(),
    )
    command_result = asyncio.run(plugin.projects_command("new Alpha"))
    assert "88" in command_result
    assert actions.ensure_private_topic.await_count == 1

    tool_result = json.loads(asyncio.run(plugin.projects_tool({
        "action": "start", "name": "Beta", "task": "Create a RAG system"
    })))
    assert tool_result["ok"] is True
    assert tool_result["thread_id"] == "99"
    assert tool_result["started"] is True
    actions.start_private_topic_task.assert_awaited_once()


def test_confirmation_is_once_only_and_unknown_outcome_is_not_retried() -> None:
    actions = SimpleNamespace(
        start_private_topic_task=AsyncMock(
            return_value={"ok": False, "error": "outcome_unknown"}
        )
    )
    service = ProjectService(actions, config_loader=lambda: {})
    with pytest.raises(RuntimeError, match="не повторяйте"):
        asyncio.run(service.start("123", "42", "Risky", "Do risky work"))
    assert actions.start_private_topic_task.await_count == 1


def test_charline_menu_uses_origin_thread_and_owner() -> None:
    actions = SimpleNamespace(
        send_card=AsyncMock(return_value={"ok": True}),
        ensure_private_topic=AsyncMock(),
    )
    source = _source(thread_id="77")
    plugin = CharlinePlugin(
        SimpleNamespace(platform_actions=actions),
        config_loader=lambda: {},
        data=FakeUiData(),
        session_key_builder=lambda captured: f"session:{captured.chat_id}:{captured.thread_id}",
    )
    plugin.capture_request(
        SimpleNamespace(source=source, text="/charline"),
        gateway=MagicMock(),
        session_store=MagicMock(),
    )
    assert asyncio.run(plugin.charline_command("")) is None
    kwargs = actions.send_card.await_args.kwargs
    assert kwargs["thread_id"] == "77"
    assert kwargs["owner_user_id"] == "42"


def test_charline_ui_is_private_chat_only() -> None:
    plugin = CharlinePlugin(SimpleNamespace(platform_actions=MagicMock()))
    plugin.capture_request(SimpleNamespace(source=_source(chat_type="group")), MagicMock())

    with pytest.raises(RuntimeError, match="личном чате"):
        asyncio.run(plugin.settings_command(""))


def test_main_home_is_compact_and_conversation_first() -> None:
    data = FakeUiData()
    data.tasks_by_session["main"] = [{"id": "d1", "label": "Анализ", "state": "running"}]
    ui = CharlineUi(ProjectService(MagicMock(), lambda: {}), data, lambda _source: "main")

    card = ui.home(_source())
    labels = [button["label"] for row in card["buttons"] for button in row]

    assert labels == ["Проекты", "Задачи", "Расписания", "Настройки"]
    assert "1 работа выполняется" in card["text"]
    assert "Что у меня сегодня?" in card["text"]
    for obsolete in (
        "Новая задача", "Новый проект", "Календарь", "Почта", "Файлы",
        "Исследование", "Память", "Сервисы", "Все функции Hermes",
    ):
        assert obsolete not in labels

    empty = CharlineUi(
        ProjectService(MagicMock(), lambda: {}), FakeUiData(), lambda _source: "main"
    ).home(_source())
    assert "Напишите, что нужно" in empty["text"]


def test_project_home_is_scoped_to_exact_native_topic() -> None:
    config = {"platforms": {"telegram": {"extra": {"dm_topics": [
        {"chat_id": "123", "topics": [{"name": "Apartment", "thread_id": 77}]}
    ]}}}}
    data = FakeUiData()
    data.tasks_by_session["project:77"] = [
        {"id": "d1", "label": "Смета", "state": "running"},
        {"id": "d2", "label": "План", "state": "waiting"},
    ]
    data.schedules_by_thread["77"] = [{"id": "job1", "name": "План недели"}]
    ui = CharlineUi(
        ProjectService(MagicMock(), lambda: config),
        data,
        lambda source: f"project:{source.thread_id}",
    )

    card = ui.home(_source(thread_id="77"))
    labels = [button["label"] for row in card["buttons"] for button in row]

    assert "Charline · Проект" in card["text"]
    assert "Apartment" in card["text"]
    assert "1 расписание" in card["text"]
    assert labels == ["В работе · 2", "Расписания · 1"]
    assert "Проекты" not in labels


def test_personal_tasks_are_not_agent_processes() -> None:
    data = FakeUiData()
    data.memories = [
        {"target": "memory", "content": "Задача: Сделать лабораторную", "digest": "task1"},
        {"target": "user", "content": "Часовой пояс — Москва", "digest": "profile1"},
    ]
    data.tasks_by_session["main"] = [
        {"id": "worker", "kind": "delegation", "label": "Фоновый агент", "state": "running"}
    ]
    ui = CharlineUi(ProjectService(MagicMock(), lambda: {}), data, lambda _source: "main")

    card = ui.personal_tasks(_source())

    assert card["text"].startswith("Задачи")
    assert "Сделать лабораторную" in card["text"]
    assert "Фоновый агент" not in card["text"]
    assert "Часовой пояс" not in card["text"]
    assert any(
        button["label"] == "Выполнено · Сделать лабораторную"
        for row in card["buttons"] for button in row
    )


def test_personal_task_completion_requires_confirmation() -> None:
    data = FakeUiData()
    data.memories = [
        {"target": "memory", "content": "Задача: Купить лампу", "digest": "task1"}
    ]
    ui = CharlineUi(ProjectService(MagicMock(), lambda: {}), data, lambda _source: "main")
    context = ui.context(_source())

    preview = ui.handle("personal_task_done.memory.task1", context)
    assert data.calls == []
    assert "Купить лампу" in preview["text"]
    result = ui.handle(preview["buttons"][0][0]["action"], context)

    assert ("memory", "memory", "task1") in data.calls
    assert "Задач пока нет" in result["text"]


def test_projects_view_owns_new_project_and_summary_is_read_only() -> None:
    config = {"platforms": {"telegram": {"extra": {"dm_topics": [
        {"chat_id": "123", "topics": [{"name": "Alpha", "thread_id": 77}]}
    ]}}}}
    projects = ProjectService(MagicMock(), lambda: config)
    data = FakeUiData()
    ui = CharlineUi(projects, data, lambda source: f"scope:{source.thread_id or 'main'}")

    project_list = ui.projects(_source())
    labels = [button["label"] for row in project_list["buttons"] for button in row]
    assert "Статус · Alpha" in labels
    assert "Как создать проект" not in labels

    summary = ui.project_summary(_source(thread_id="77"), "77")
    assert "Alpha" in summary["text"]
    assert data.tasks_by_session == {}
    assert all(
        button["label"] != "В работе"
        for row in summary["buttons"] for button in row
    )


def test_cross_project_views_remain_read_only_and_keep_explicit_scope() -> None:
    config = {"platforms": {"telegram": {"extra": {"dm_topics": [
        {"chat_id": "123", "topics": [{"name": "Alpha", "thread_id": 77}]}
    ]}}}}
    data = FakeUiData()
    data.tasks_by_session["scope:77"] = [
        {"id": "deleg_1", "kind": "delegation", "label": "Работа", "state": "running"}
    ]
    data.schedules_by_thread["77"] = [{"id": "job1", "name": "План"}]
    ui = CharlineUi(
        ProjectService(MagicMock(), lambda: config), data,
        lambda source: f"scope:{source.thread_id or 'main'}",
    )

    root = _source()
    summary = ui.project_summary(root, "77")
    summary_actions = [button["action"] for row in summary["buttons"] for button in row]
    assert "project_tasks.77" in summary_actions
    assert "project_schedules.77" not in summary_actions

    tasks = ui.handle("project_tasks.77", ui.context(root))
    actions = [button["action"] for row in tasks["buttons"] for button in row]
    assert "Работа" in tasks["text"]
    assert "project_tasks.77" in actions
    assert "summary.77" in actions
    assert not any(action.startswith("task_stop.") for action in actions)


def test_project_index_pages_are_bounded_and_reconstructable() -> None:
    topics = [{"name": f"Project {index}", "thread_id": index} for index in range(1, 12)]
    config = {"platforms": {"telegram": {"extra": {"dm_topics": [
        {"chat_id": "123", "topics": topics}
    ]}}}}
    ui = CharlineUi(
        ProjectService(MagicMock(), lambda: config), FakeUiData(),
        lambda source: f"scope:{source.thread_id or 'main'}",
    )

    first = ui.projects(_source())
    assert "Project 1" in first["text"]
    assert "Project 9" not in first["text"]
    second = ui.handle("projects.2", ui.context(_source()))
    assert "Project 9" in second["text"]
    assert "Project 1\n" not in second["text"]


def test_tasks_are_current_scope_only_and_hide_fast_foreground_work() -> None:
    data = FakeUiData()
    data.tasks_by_session["main"] = [
        {"id": "foreground", "label": "Текущий ответ", "state": "foreground"},
        {"id": "deleg_1", "kind": "delegation", "label": "Исследование", "state": "running"},
    ]
    data.tasks_by_session["project"] = [
        {"id": "deleg_2", "kind": "delegation", "label": "Чужой проект", "state": "running"}
    ]
    ui = CharlineUi(
        ProjectService(MagicMock(), lambda: {}),
        data,
        lambda source: "project" if source.thread_id else "main",
    )

    main = ui.tasks(_source())
    assert "Исследование" in main["text"]
    assert "Текущий ответ" not in main["text"]
    assert "Чужой проект" not in main["text"]


def test_realistic_long_entity_ids_keep_callback_actions_short() -> None:
    data = FakeUiData()
    long_id = "entity-" + "x" * 80
    data.tasks_by_session["main"] = [
        {"id": long_id, "kind": "delegation", "label": "Исследование", "state": "running"}
    ]
    data.schedules_by_thread[""] = [{
        "id": long_id, "name": "Утренний план", "enabled": True, "display": "08:30"
    }]
    ui = CharlineUi(ProjectService(MagicMock(), lambda: {}), data, lambda _source: "main")

    cards = [ui.tasks(_source()), ui.schedules(_source())]
    actions = [button["action"] for card in cards for row in card["buttons"] for button in row]

    assert all(len(action) <= 36 for action in actions)
    assert long_id not in " ".join(actions)


def test_task_states_are_human_readable_and_single_stop_is_confirmed() -> None:
    data = FakeUiData()
    data.tasks_by_session["main"] = [
        {"id": "d1", "kind": "delegation", "label": "Отчёт", "state": "finalizing"},
        {"id": "d2", "kind": "delegation", "label": "Поиск", "state": "stalling"},
    ]
    ui = CharlineUi(ProjectService(MagicMock(), lambda: {}), data, lambda _source: "main")
    context = ui.context(_source())

    card = ui.tasks(_source())
    assert card["text"].startswith("В работе")
    assert "завершается" in card["text"]
    assert "задерживается" in card["text"]

    stop_action = next(
        button["action"] for row in card["buttons"] for button in row
        if button["label"].startswith("Остановить · Отчёт")
    )
    preview = ui.handle(stop_action, context)
    assert "Отчёт" in preview["text"]
    assert data.calls == []
    ui.handle(preview["buttons"][0][0]["action"], context)
    assert ("stop_task", "main", "delegation", "d1") in data.calls


def test_schedules_list_details_and_settings_memory_are_reconstructable() -> None:
    data = FakeUiData()
    data.schedules_by_thread[""] = [{
        "id": "job123", "name": "Утренний план", "display": "будни · 08:30",
        "enabled": True, "next_run_at": "завтра, 08:30", "last_run_at": "сегодня",
        "last_status": "ok",
    }]
    data.memories = [{"target": "user", "content": "Часовой пояс — Москва", "digest": "abc123"}]
    ui = CharlineUi(ProjectService(MagicMock(), lambda: {}), data, lambda _source: "main")

    schedules = ui.schedules(_source())
    assert schedules["text"].startswith("Расписания")
    assert "Утренний план" in schedules["text"]
    assert "Следующий запуск: завтра, 08:30" in schedules["text"]
    assert "Как создать расписание" not in [
        button["label"] for row in schedules["buttons"] for button in row
    ]
    detail = ui.handle("schedule.job123", ui.context(_source()))
    assert "Когда: будни · 08:30" in detail["text"]
    assert "Следующий запуск: завтра, 08:30" in detail["text"]
    assert "сегодня · успешно" in detail["text"]

    settings = ui.settings(_source())
    labels = [button["label"] for row in settings["buttons"] for button in row]
    assert labels == ["Память", "Расписания", "Назад"]
    assert "Внешние действия всегда требуют подтверждения" in settings["text"]
    automations_action = settings["buttons"][1][0]["action"]
    automations = ui.handle(automations_action, ui.context(_source()))
    assert automations["buttons"][-1][0] == {"label": "Назад", "action": "settings"}
    memory = ui.handle("memory", ui.context(_source()))
    assert "Часовой пояс" in memory["text"]
    assert "Запомнить" not in memory["text"]
    assert "Забыть" not in memory["text"]


def test_unnamed_automation_button_names_the_object_not_a_vague_action() -> None:
    data = FakeUiData()
    data.schedules_by_thread[""] = [{
        "id": "job123", "name": "", "display": "будни · 08:30",
        "enabled": True, "next_run_at": "завтра, 08:30",
    }]
    ui = CharlineUi(ProjectService(MagicMock(), lambda: {}), data, lambda _source: "main")

    labels = [button["label"] for row in ui.schedules(_source())["buttons"] for button in row]

    assert labels[0] == "Расписание"
    assert "Подробнее" not in labels


def test_read_navigation_is_stateless_but_mutation_confirmation_expires() -> None:
    data = FakeUiData()
    data.tasks_by_session["main"] = [
        {"id": "deleg_1", "kind": "delegation", "label": "Работа", "state": "running"}
    ]
    ui = CharlineUi(ProjectService(MagicMock(), lambda: {}), data, lambda _source: "main")
    context = ui.context(_source())

    assert "Проекты" in ui.handle("projects", context)["text"]
    preview = ui.handle("tasks.stop_all", context)
    confirm_action = preview["buttons"][0][0]["action"]
    assert confirm_action.startswith("tasks.confirm.")

    restarted = CharlineUi(ProjectService(MagicMock(), lambda: {}), data, lambda _source: "main")
    expired = restarted.handle(confirm_action, context)
    assert "больше не актуальна" in expired["text"]


def test_stop_all_schedule_delete_and_memory_delete_require_confirmation() -> None:
    data = FakeUiData()
    data.tasks_by_session["main"] = [
        {"id": "deleg_1", "kind": "delegation", "label": "Работа", "state": "running"}
    ]
    data.schedules_by_thread[""] = [{
        "id": "job1", "name": "План", "enabled": True, "display": "08:30"
    }]
    data.memories = [{"target": "user", "content": "Москва", "digest": "abc"}]
    ui = CharlineUi(ProjectService(MagicMock(), lambda: {}), data, lambda _source: "main")
    context = ui.context(_source())

    stop_preview = ui.handle("tasks.stop_all", context)
    assert data.calls == []
    ui.handle(stop_preview["buttons"][0][0]["action"], context)
    assert data.calls == [("stop_all", "main")]

    schedule_preview = ui.handle("schedule_delete.job1", context)
    assert not any(call[0] == "schedule" for call in data.calls)
    ui.handle(schedule_preview["buttons"][0][0]["action"], context)
    assert ("schedule", "", "job1", "delete") in data.calls
    assert data.schedules_by_thread[""] == []

    memory_preview = ui.handle("memory_delete.user.abc", context)
    assert not any(call[0] == "memory" for call in data.calls)
    assert "Москва" in memory_preview["text"]
    ui.handle(memory_preview["buttons"][0][0]["action"], context)
    assert ("memory", "user", "abc") in data.calls
    assert data.memories == []


@pytest.mark.parametrize(
    ("action", "verb"),
    [
        ("schedule_pause.job1", "pause"),
        ("schedule_resume.job1", "resume"),
        ("schedule_run.job1", "run"),
    ],
)
def test_every_schedule_mutation_requires_confirmation(action, verb) -> None:
    data = FakeUiData()
    data.schedules_by_thread[""] = [{
        "id": "job1", "name": "План", "enabled": verb == "resume", "display": "08:30"
    }]
    ui = CharlineUi(ProjectService(MagicMock(), lambda: {}), data, lambda _source: "main")
    context = ui.context(_source())

    preview = ui.handle(action, context)

    assert data.calls == []
    confirm_action = preview["buttons"][0][0]["action"]
    assert confirm_action.startswith("schedule_confirm.")
    ui.handle(confirm_action, context)
    assert ("schedule", "", "job1", verb) in data.calls
    if verb == "run":
        result = ui.handle(action, context)
        result = ui.handle(result["buttons"][0][0]["action"], context)
        assert "Запуск поставлен в очередь" in result["text"]


def test_pending_decision_points_back_to_the_original_question() -> None:
    data = FakeUiData()
    data.pending_by_session["main"] = 1
    ui = CharlineUi(ProjectService(MagicMock(), lambda: {}), data, lambda _source: "main")

    card = ui.tasks(_source())

    assert "Вернитесь к сообщению с вопросом выше" in card["text"]


def test_read_failures_are_not_reported_as_empty_state() -> None:
    data = FakeUiData()
    data.tasks_available = False
    data.schedules_available = False
    data.memory_available = False
    ui = CharlineUi(ProjectService(MagicMock(), lambda: {}), data, lambda _source: "main")

    assert "Не удалось загрузить текущую работу" in ui.tasks(_source())["text"]
    assert "Не удалось загрузить расписания" in ui.schedules(_source())["text"]
    assert "Не удалось загрузить память" in ui.memory(_source())["text"]


def test_agent_processes_do_not_replace_personal_tasks_in_main_navigation() -> None:
    data = FakeUiData()
    data.tasks_by_session["main"] = [
        {"id": "d1", "kind": "delegation", "label": "Работа", "state": "running"}
    ]
    ui = CharlineUi(ProjectService(MagicMock(), lambda: {}), data, lambda _source: "main")
    active = ui.home(_source())
    assert all(button["action"] != "tasks" for row in active["buttons"] for button in row)
    assert any(button["action"] == "personal_tasks" for row in active["buttons"] for button in row)

    data.tasks_by_session["main"] = []
    idle = ui.home(_source())
    assert all(button["action"] != "tasks" for row in idle["buttons"] for button in row)


def test_daily_ui_has_no_generic_force_reply_launchers() -> None:
    ui = CharlineUi(ProjectService(MagicMock(), lambda: {}), FakeUiData(), lambda _source: "main")
    cards = [
        ui.home(_source()), ui.projects(_source()), ui.personal_tasks(_source()),
        ui.tasks(_source()), ui.schedules(_source()), ui.settings(_source()),
    ]
    assert all("force_reply" not in card for card in cards)


def test_ui_callback_reconstructs_exact_callback_chat_and_thread() -> None:
    actions = SimpleNamespace(send_card=AsyncMock(), ensure_private_topic=AsyncMock())
    plugin = CharlinePlugin(
        SimpleNamespace(platform_actions=actions),
        config_loader=lambda: {},
        data=FakeUiData(),
        session_key_builder=lambda source: f"{source.chat_id}:{source.thread_id}",
    )
    plugin.capture_request(SimpleNamespace(source=_source(thread_id="77")), MagicMock())

    card = plugin.ui_callback("home", {
        "platform": "telegram", "chat_id": "999", "thread_id": "77", "user_id": "42"
    })
    assert "Charline" in card["text"]
    assert plugin.platform_event(
        platform="telegram", event_type="plugin_callback",
        payload={"plugin": "other", "action": "home"},
    ) is None


def test_group_callback_cannot_reveal_private_memory() -> None:
    data = FakeUiData()
    data.memories = [{"target": "user", "content": "private value", "digest": "abc"}]
    plugin = CharlinePlugin(
        SimpleNamespace(platform_actions=MagicMock()), data=data, config_loader=lambda: {}
    )

    card = plugin.ui_callback("memory", {
        "platform": "telegram", "chat_id": "123", "chat_type": "group", "user_id": "42"
    })

    assert "личном чате" in card["text"]
    assert "private value" not in card["text"]
