"""Native-project service over Hermes-owned Telegram topic metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping


class ProjectNameError(ValueError):
    """Raised when a Telegram project title is invalid."""


@dataclass(frozen=True)
class NativeProject:
    name: str
    thread_id: str


@dataclass(frozen=True)
class ProjectCreation:
    name: str
    thread_id: str


def build_project_handoff(name: str, original_request: str) -> str:
    """Build Charline's product handoff without teaching Hermes about projects."""
    return (
        f"Continue the owner's request in the native Telegram project topic “{name}”.\n\n"
        f"Original request:\n{original_request}\n\n"
        "Treat this message as the beginning of the project conversation. Ask only "
        "clarifications that are genuinely required, then plan and continue through a "
        "verified result. Use normal Hermes capabilities and choose direct work, "
        "delegation, background execution or durable Kanban according to the work itself."
    )


def normalize_project_name(value: str) -> str:
    """Normalize a Telegram topic title without changing its meaning."""
    if not isinstance(value, str) or any(char in value for char in "\r\n"):
        raise ProjectNameError("Название проекта должно быть в одной строке.")
    name = re.sub(r"[ \t]+", " ", value).strip()
    if not name:
        raise ProjectNameError("Укажите название проекта.")
    if len(name) > 128:
        raise ProjectNameError("Название проекта не должно превышать 128 символов.")
    return name


def list_native_projects(
    config: Mapping[str, Any], chat_id: str
) -> list[NativeProject]:
    """Return persisted native topics for one owner chat, without side effects."""
    try:
        entries = config["platforms"]["telegram"]["extra"]["dm_topics"]
    except (KeyError, TypeError):
        return []
    if not isinstance(entries, list):
        return []
    result: list[NativeProject] = []
    for entry in entries:
        if not isinstance(entry, Mapping) or str(entry.get("chat_id")) != str(chat_id):
            continue
        topics = entry.get("topics")
        if not isinstance(topics, list):
            continue
        for topic in topics:
            if not isinstance(topic, Mapping):
                continue
            name = topic.get("name")
            thread_id = topic.get("thread_id")
            if isinstance(name, str) and name.strip() and str(thread_id).isdigit():
                result.append(NativeProject(name.strip(), str(thread_id)))
    return result


class ProjectService:
    """One implementation shared by commands, buttons and model tools."""

    def __init__(self, platform_actions: Any, config_loader: Callable[[], Mapping[str, Any]]):
        self._actions = platform_actions
        self._config_loader = config_loader

    def list(self, chat_id: str) -> list[NativeProject]:
        return list_native_projects(self._config_loader(), chat_id)

    async def create(self, chat_id: str, raw_name: str) -> ProjectCreation:
        name = normalize_project_name(raw_name)
        result = await self._actions.ensure_private_topic("telegram", str(chat_id), name)
        return self._verified_creation(chat_id, name, result)

    async def start(
        self, chat_id: str, user_id: str, raw_name: str, task: str
    ) -> ProjectCreation:
        name = normalize_project_name(raw_name)
        task = str(task or "").strip()
        if not task:
            raise ValueError("Укажите исходную задачу проекта.")
        ensured = await self._actions.ensure_private_topic(
            "telegram", str(chat_id), name
        )
        created = self._verified_creation(chat_id, name, ensured)
        dispatched = await self._actions.dispatch_agent_turn(
            platform="telegram",
            chat_id=str(chat_id),
            thread_id=created.thread_id,
            owner_user_id=str(user_id),
            prompt=build_project_handoff(name, task),
        )
        if not dispatched.get("ok"):
            detail = dispatched.get("detail") or dispatched.get("error") or "unknown error"
            raise RuntimeError(
                f"Проект создан, но работу в его теме запустить не удалось: {detail}"
            )
        return created

    def _verified_creation(
        self,
        chat_id: str,
        name: str,
        result: Mapping[str, Any],
    ) -> ProjectCreation:
        if not result.get("ok") or not result.get("thread_id"):
            detail = result.get("detail") or result.get("error") or "unknown error"
            if result.get("error") == "outcome_unknown":
                raise RuntimeError(
                    "Результат создания неизвестен; не повторяйте запись. "
                    "Сначала проверьте Telegram и dm_topics вручную."
                )
            raise RuntimeError(f"Не удалось создать проект: {detail}")
        thread_id = str(result["thread_id"])
        verified = any(
            item.name == name and item.thread_id == thread_id
            for item in self.list(str(chat_id))
        )
        if not verified:
            raise RuntimeError(
                "Проект мог быть создан, но read-back dm_topics не подтвердил результат; "
                "не повторяйте запись до ручной проверки."
            )
        return ProjectCreation(name=name, thread_id=thread_id)
