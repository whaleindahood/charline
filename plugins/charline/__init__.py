"""Charline product UX as a Hermes plugin, not a second runtime."""

from __future__ import annotations

import contextvars
import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Optional

from .projects import ProjectNameError, ProjectService
from .ui import CharlineUi


@dataclass(frozen=True)
class RequestContext:
    source: Any


_REQUEST: contextvars.ContextVar[Optional[RequestContext]] = contextvars.ContextVar(
    "charline_request", default=None
)


def _default_config_loader() -> Mapping[str, Any]:
    from hermes_cli.config import load_config_readonly

    return load_config_readonly()


class CharlinePlugin:
    """Thin product layer over Hermes commands, tools and Telegram topics."""

    def __init__(
        self,
        ctx: Any,
        config_loader: Callable[[], Mapping[str, Any]] = _default_config_loader,
        data: Any = None,
        session_key_builder: Callable[[Any], str] | None = None,
    ):
        self.actions = ctx.platform_actions
        self.projects = ProjectService(ctx.platform_actions, config_loader)
        self.ui = CharlineUi(self.projects, data, session_key_builder)

    def capture_request(self, event: Any, gateway: Any, session_store: Any = None, **_: Any) -> None:
        """Capture immutable routing context; never rewrite or route a message."""
        del session_store
        del gateway
        _REQUEST.set(RequestContext(source=event.source))
        return None

    def current_request(self) -> RequestContext:
        request = _REQUEST.get()
        if request is None:
            raise RuntimeError("Команда доступна только из активного Gateway-чата.")
        return request

    @staticmethod
    def _telegram_source(request: RequestContext) -> Any:
        source = request.source
        platform = getattr(getattr(source, "platform", None), "value", "")
        if platform != "telegram" or not getattr(source, "chat_id", None):
            raise RuntimeError("Проекты Charline V1 доступны в Telegram.")
        if str(getattr(source, "chat_type", "") or "").lower() not in {"dm", "private"}:
            raise RuntimeError("Интерфейс Charline доступен только в личном чате с ботом.")
        return source

    async def projects_command(self, raw_args: str) -> str:
        request = self.current_request()
        source = self._telegram_source(request)
        args = (raw_args or "").strip()
        head, _, tail = args.partition(" ")
        if head.casefold() == "new":
            try:
                preview = self.projects.prepare(
                    source.chat_id, source.user_id, tail,
                    str(getattr(source, "thread_id", None) or ""),
                )
            except ProjectNameError as exc:
                return str(exc)
            return (
                f"Точное действие: Создать Telegram-проект «{preview.name}».\n"
                "Это создаст внешний Telegram topic. Для явного подтверждения: "
                f"/projects confirm {preview.digest}"
            )
        if head.casefold() == "confirm":
            try:
                created = await self.projects.confirm(
                    source.chat_id, source.user_id, tail,
                    str(getattr(source, "thread_id", None) or ""),
                )
            except RuntimeError as exc:
                return str(exc)
            return (
                f"✅ Проект «{created.name}» создан. "
                f"Откройте новый Telegram topic (thread {created.thread_id})."
            )
        if args:
            return "Использование: /projects или /projects new <название>"
        return await self._send_card(self.ui.projects(source), source)

    def projects_tool(self, params: Mapping[str, Any], **_: Any) -> str:
        """Prepare a safe project action; the write stays behind explicit command confirmation."""
        action = str(params.get("action") or "list")
        if action == "prepare_create":
            try:
                source = self._telegram_source(self.current_request())
                preview = self.projects.prepare(
                    source.chat_id,
                    source.user_id,
                    str(params.get("name") or ""),
                    str(getattr(source, "thread_id", None) or ""),
                )
            except (ProjectNameError, RuntimeError) as exc:
                return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
            return json.dumps(
                {
                    "ok": True,
                    "confirmation_required": True,
                    "preview": f"Создать Telegram-проект «{preview.name}»",
                    "confirmation_command": f"/projects confirm {preview.digest}",
                },
                ensure_ascii=False,
            )
        if action == "list":
            try:
                source = self._telegram_source(self.current_request())
                projects = self.projects.list(source.chat_id)
            except RuntimeError as exc:
                return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
            return json.dumps(
                {
                    "ok": True,
                    "projects": [
                        {"name": item.name, "thread_id": item.thread_id}
                        for item in projects
                    ],
                },
                ensure_ascii=False,
            )
        return json.dumps({"ok": False, "error": "unknown action"})

    async def _send_card(self, card: Mapping[str, Any], source: Any) -> None | str:
        result = await self.actions.send_card(
            platform="telegram",
            chat_id=str(source.chat_id),
            text=str(card.get("text") or ""),
            buttons=list(card.get("buttons") or []),
            thread_id=str(source.thread_id) if getattr(source, "thread_id", None) is not None else "",
            owner_user_id=str(source.user_id or ""),
        )
        if result.get("ok"):
            return None
        return "Не удалось открыть этот раздел. Попробуйте команду ещё раз."

    async def charline_command(self, raw_args: str) -> None | str:
        if (raw_args or "").strip():
            return "Использование: /charline"
        source = self._telegram_source(self.current_request())
        return await self._send_card(self.ui.home(source), source)

    async def today_command(self, raw_args: str) -> None | str:
        if (raw_args or "").strip():
            return "Использование: /today"
        source = self._telegram_source(self.current_request())
        return await self._send_card(self.ui.today(source), source)

    async def tasks_command(self, raw_args: str) -> None | str:
        if (raw_args or "").strip():
            return "Использование: /tasks"
        source = self._telegram_source(self.current_request())
        return await self._send_card(self.ui.tasks(source), source)

    async def schedules_command(self, raw_args: str) -> None | str:
        if (raw_args or "").strip():
            return "Использование: /schedules"
        source = self._telegram_source(self.current_request())
        return await self._send_card(self.ui.schedules(source), source)

    async def settings_command(self, raw_args: str) -> None | str:
        if (raw_args or "").strip():
            return "Использование: /settings"
        source = self._telegram_source(self.current_request())
        return await self._send_card(self.ui.settings(source), source)

    @staticmethod
    def _callback_source(context: Mapping[str, Any]) -> Any:
        try:
            from gateway.config import Platform
            from gateway.session import SessionSource

            return SessionSource(
                platform=Platform.TELEGRAM,
                chat_id=str(context.get("chat_id") or ""),
                chat_type=str(context.get("chat_type") or "dm"),
                user_id=str(context.get("user_id") or ""),
                thread_id=str(context["thread_id"]) if context.get("thread_id") not in {None, ""} else None,
            )
        except ImportError:
            return SimpleNamespace(
                platform=SimpleNamespace(value="telegram"),
                chat_id=str(context.get("chat_id") or ""),
                chat_type=str(context.get("chat_type") or "dm"),
                user_id=str(context.get("user_id") or ""),
                thread_id=str(context["thread_id"]) if context.get("thread_id") not in {None, ""} else None,
            )

    def ui_callback(self, action: str, context: Mapping[str, Any]) -> dict[str, Any]:
        source = self._callback_source(context)
        try:
            self._telegram_source(RequestContext(source=source))
        except RuntimeError as exc:
            return {"text": str(exc), "buttons": []}
        return self.ui.handle(str(action or ""), self.ui.context(source))

    def platform_event(
        self,
        platform: str = "",
        event_type: str = "",
        payload: Mapping[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any] | None:
        payload = payload or {}
        if platform != "telegram" or event_type != "plugin_callback" or payload.get("plugin") != "charline":
            return None
        card = self.ui_callback(str(payload.get("action") or ""), payload)
        return {"plugin": "charline", "card": card}


def register(ctx: Any) -> None:
    plugin = CharlinePlugin(ctx)
    ctx.register_hook("pre_gateway_dispatch", plugin.capture_request)
    ctx.register_hook("gateway_platform_event", plugin.platform_event)
    ctx.register_command(
        name="charline",
        handler=plugin.charline_command,
        description="Открыть меню личного ассистента Charline",
    )
    ctx.register_command(
        name="projects",
        handler=plugin.projects_command,
        description="Показать или создать Telegram-проект",
        args_hint="[new <название> | confirm <код>]",
    )
    ctx.register_command(
        name="today",
        handler=plugin.today_command,
        description="Сегодня",
    )
    ctx.register_command(
        name="charline-tasks",
        handler=plugin.tasks_command,
        description="Задачи",
    )
    ctx.register_command(
        name="schedules",
        handler=plugin.schedules_command,
        description="Расписания",
    )
    ctx.register_command(
        name="settings",
        handler=plugin.settings_command,
        description="Настройки",
    )
    ctx.register_tool(
        name="charline_projects",
        toolset="charline",
        schema={
            "name": "charline_projects",
            "description": (
                "List native Charline Telegram projects or prepare an exact project "
                "creation preview. Creation is never performed by this tool: after "
                "the user confirms the preview, use the returned /projects confirm command."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "prepare_create"]},
                    "name": {"type": "string"},
                },
                "required": ["action"],
            },
        },
        handler=plugin.projects_tool,
    )
