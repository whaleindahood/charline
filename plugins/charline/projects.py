"""Native-project service over Hermes-owned Telegram topic metadata."""

from __future__ import annotations

import re
import time
from collections import OrderedDict
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


@dataclass(frozen=True)
class ProjectPreview:
    name: str
    digest: str


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
        self._pending: OrderedDict[tuple[str, str, str, str], tuple[float, str]] = OrderedDict()

    def list(self, chat_id: str) -> list[NativeProject]:
        return list_native_projects(self._config_loader(), chat_id)

    def prepare(
        self, chat_id: str, user_id: str, raw_name: str, thread_id: str = ""
    ) -> ProjectPreview:
        name = normalize_project_name(raw_name)
        digest = sha256(
            f"{chat_id}\0{thread_id}\0{user_id}\0{name}".encode("utf-8")
        ).hexdigest()[:16]
        key = (str(chat_id), str(thread_id or ""), str(user_id), digest)
        self._pending[key] = (time.monotonic(), name)
        self._pending.move_to_end(key)
        while len(self._pending) > 64:
            self._pending.popitem(last=False)
        return ProjectPreview(name=name, digest=digest)

    async def confirm(
        self, chat_id: str, user_id: str, digest: str, thread_id: str = ""
    ) -> ProjectCreation:
        key = (str(chat_id), str(thread_id or ""), str(user_id), str(digest).strip())
        pending = self._pending.pop(key, None)
        if pending is None or time.monotonic() - pending[0] > 600:
            raise RuntimeError("Подтверждение устарело. Сначала снова покажите preview.")
        name = pending[1]
        result = await self._actions.ensure_private_topic("telegram", str(chat_id), name)
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
