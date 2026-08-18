"""Native-project service over Hermes-owned Telegram topic metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
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
    request_id: str = ""


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
        request_id = "charline-" + sha256(
            f"{chat_id}\0{name}\0{task}".encode("utf-8")
        ).hexdigest()[:16]
        result = await self._actions.start_private_topic_task(
            "telegram",
            str(chat_id),
            name,
            task,
            owner_user_id=str(user_id),
            request_id=request_id,
        )
        return self._verified_creation(chat_id, name, result, request_id=request_id)

    def _verified_creation(
        self,
        chat_id: str,
        name: str,
        result: Mapping[str, Any],
        *,
        request_id: str = "",
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
        return ProjectCreation(name=name, thread_id=thread_id, request_id=request_id)
