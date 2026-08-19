from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from plugins.charline import CharlinePlugin, register
from plugins.charline.projects import (
    ProjectNameError,
    ProjectService,
    list_native_projects,
    normalize_project_name,
)
from plugins.charline.ui import CharlineUi


def _source(*, thread_id=None, chat_type="dm", user_id="42"):
    return SimpleNamespace(
        platform=SimpleNamespace(value="telegram"),
        chat_id="123",
        thread_id=thread_id,
        user_id=user_id,
        chat_type=chat_type,
    )


class FakeUiData:
    def __init__(self):
        self.tasks = []
        self.reminders = []
        self.available = True
        self.deleted = []

    def personal_tasks(self):
        return list(self.tasks) if self.available else None

    def upcoming_reminders(self, source):
        del source
        return list(self.reminders) if self.available else None

    def delete_memory(self, target, digest):
        self.deleted.append((target, digest))
        before = len(self.tasks)
        self.tasks = [
            item for item in self.tasks
            if not (item["target"] == target and item["digest"] == digest)
        ]
        return len(self.tasks) < before


def test_project_name_normalization() -> None:
    assert normalize_project_name("  Project   Alpha  ") == "Project Alpha"
    with pytest.raises(ProjectNameError):
        normalize_project_name("bad\nname")
    with pytest.raises(ProjectNameError):
        normalize_project_name("x" * 129)


def test_project_index_is_native_dm_topics_read_model() -> None:
    config = {"platforms": {"telegram": {"extra": {"dm_topics": [
        {"chat_id": 123, "topics": [
            {"name": "Alpha", "thread_id": 11},
            {"name": "Pending", "thread_id": "auto"},
        ]},
        {"chat_id": 999, "topics": [{"name": "Foreign", "thread_id": 99}]},
    ]}}}}
    assert [(p.name, p.thread_id) for p in list_native_projects(config, "123")] == [
        ("Alpha", "11")
    ]


def test_project_start_composes_generic_topic_and_dispatch_actions() -> None:
    config = {"platforms": {"telegram": {"extra": {"dm_topics": []}}}}

    async def ensure(_platform, chat_id, name):
        config["platforms"]["telegram"]["extra"]["dm_topics"] = [
            {"chat_id": chat_id, "topics": [{"name": name, "thread_id": 77}]}
        ]
        return {"ok": True, "thread_id": "77"}

    actions = SimpleNamespace(
        ensure_private_topic=AsyncMock(side_effect=ensure),
        dispatch_agent_turn=AsyncMock(return_value={"ok": True}),
    )
    result = asyncio.run(ProjectService(actions, lambda: config).start(
        "123", "42", " Project  Alpha ", "Build and test the website"
    ))

    assert result.thread_id == "77"
    actions.ensure_private_topic.assert_awaited_once_with("telegram", "123", "Project Alpha")
    call = actions.dispatch_agent_turn.await_args.kwargs
    assert call["thread_id"] == "77"
    assert call["owner_user_id"] == "42"
    assert "Build and test the website" in call["prompt"]
    assert "Project Alpha" in call["prompt"]


def test_project_start_does_not_dispatch_after_unknown_topic_outcome() -> None:
    actions = SimpleNamespace(
        ensure_private_topic=AsyncMock(return_value={"ok": False, "error": "outcome_unknown"}),
        dispatch_agent_turn=AsyncMock(),
    )
    with pytest.raises(RuntimeError, match="не повторяйте"):
        asyncio.run(ProjectService(actions, lambda: {}).start(
            "123", "42", "Risky", "Do work"
        ))
    actions.dispatch_agent_turn.assert_not_awaited()


def test_projects_command_and_tool_share_service() -> None:
    config = {"platforms": {"telegram": {"extra": {"dm_topics": []}}}}

    async def ensure(_platform, chat_id, name):
        config["platforms"]["telegram"]["extra"]["dm_topics"] = [
            {"chat_id": chat_id, "topics": [{"name": name, "thread_id": 88}]}
        ]
        return {"ok": True, "thread_id": "88"}

    actions = SimpleNamespace(
        ensure_private_topic=AsyncMock(side_effect=ensure),
        dispatch_agent_turn=AsyncMock(return_value={"ok": True}),
        send_card=AsyncMock(return_value={"ok": True}),
    )
    plugin = CharlinePlugin(SimpleNamespace(platform_actions=actions), lambda: config)
    plugin.capture_request(SimpleNamespace(source=_source(), text="/projects new Alpha"), MagicMock())
    assert "88" in asyncio.run(plugin.projects_command("new Alpha"))

    result = json.loads(asyncio.run(plugin.projects_tool({
        "action": "start", "name": "Alpha", "task": "Create a RAG system"
    })))
    assert result == {"ok": True, "started": True, "name": "Alpha", "thread_id": "88"}
    actions.dispatch_agent_turn.assert_awaited_once()


def test_plugin_registers_only_four_daily_views_and_generic_hooks() -> None:
    ctx = MagicMock()
    ctx.platform_actions = MagicMock()
    register(ctx)
    assert {call.kwargs["name"] for call in ctx.register_command.call_args_list} == {
        "charline", "charline-tasks", "projects", "settings", "today"
    }
    assert [call.args[0] for call in ctx.register_hook.call_args_list] == [
        "pre_gateway_dispatch", "post_auth_pre_agent_dispatch", "gateway_platform_event"
    ]


def test_root_and_topics_keep_their_exact_context() -> None:
    plugin = CharlinePlugin(SimpleNamespace(platform_actions=MagicMock()))
    root = SimpleNamespace(source=_source(), text="hello")
    project = SimpleNamespace(source=_source(thread_id="77"), text="hello")
    assert plugin.capture_request(root, MagicMock()) is None
    assert plugin.current_request().source.thread_id is None
    assert plugin.capture_request(project, MagicMock()) is None
    assert plugin.current_request().source.thread_id == "77"
    assert root.text == project.text == "hello"


def test_daily_ui_has_four_views_without_runtime_admin_controls() -> None:
    data = FakeUiData()
    ui = CharlineUi(ProjectService(MagicMock(), lambda: {}), data, timezone_loader=lambda: "Europe/Paris")
    card = ui.home(_source())
    labels = [button["label"] for row in card["buttons"] for button in row]
    assert labels == ["Сегодня", "Проекты", "Задачи", "Настройки"]
    assert not ({"Расписания", "Память", "Процессы"} & set(labels))
    settings = ui.settings(_source())
    assert "Europe/Paris" in settings["text"]
    assert settings["buttons"] == [[{"label": "Назад", "action": "home"}]]


def test_today_is_deterministic_and_does_not_start_agent_turn() -> None:
    data = FakeUiData()
    data.tasks = [{"title": "Купить лампу", "target": "memory", "digest": "a"}]
    data.reminders = [{"name": "Weekly review", "next_run_at": "2026-08-24T09:00:00+03:00"}]
    actions = SimpleNamespace(send_card=AsyncMock(return_value={"ok": True}), dispatch_agent_turn=AsyncMock())
    today = SimpleNamespace(card=AsyncMock(return_value={
        "text": "Сегодня\n\n• Купить лампу\n• Weekly review", "buttons": []
    }))
    plugin = CharlinePlugin(
        SimpleNamespace(platform_actions=actions), lambda: {}, data=data, today_service=today
    )
    plugin.capture_request(SimpleNamespace(source=_source(), text="/today"), MagicMock())

    assert asyncio.run(plugin.today_command("")) is None
    sent = actions.send_card.await_args.kwargs["text"]
    assert "Купить лампу" in sent
    assert "Weekly review" in sent
    actions.dispatch_agent_turn.assert_not_awaited()


def test_personal_task_confirmation_is_owner_bound_and_once_only() -> None:
    data = FakeUiData()
    data.tasks = [{"title": "Купить лампу", "target": "memory", "digest": "a"}]
    ui = CharlineUi(ProjectService(MagicMock(), lambda: {}), data)
    preview = ui.handle("personal_task_done.memory.a", ui.context(_source()))
    action = preview["buttons"][0][0]["action"]

    wrong = ui.handle(action, ui.context(_source(user_id="99")))
    assert "не актуальна" in wrong["text"]
    assert data.deleted == []

    preview = ui.handle("personal_task_done.memory.a", ui.context(_source()))
    action = preview["buttons"][0][0]["action"]
    done = ui.handle(action, ui.context(_source()))
    assert "Задача выполнена" in done["text"]
    assert data.deleted == [("memory", "a")]
    again = ui.handle(action, ui.context(_source()))
    assert "не актуальна" in again["text"]


def test_ui_is_private_chat_only() -> None:
    plugin = CharlinePlugin(SimpleNamespace(platform_actions=MagicMock()))
    plugin.capture_request(SimpleNamespace(source=_source(chat_type="group")), MagicMock())
    with pytest.raises(RuntimeError, match="личном чате"):
        asyncio.run(plugin.settings_command(""))
