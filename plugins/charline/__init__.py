"""Charline product UX as a Hermes plugin, not a second runtime."""

from __future__ import annotations

import contextvars
import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Optional

from .projects import ProjectNameError, ProjectService
from .ui import CharlineUi
from .calendar import CalendarFastPath, _default_now, _default_timezone
from .today import TodayService


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
        today_service: Any = None,
    ):
        self.actions = ctx.platform_actions
        self._ctx = ctx
        self.projects = ProjectService(ctx.platform_actions, config_loader)
        self.ui = CharlineUi(self.projects, data)
        self.today = today_service or TodayService(
            self.projects,
            self.ui.data,
            now=_default_now,
            timezone_loader=_default_timezone,
        )
        self.calendar = (
            CalendarFastPath(ctx)
            if all(hasattr(ctx, name) for name in ("llm", "state", "spawn_task"))
            else None
        )

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
                created = await self.projects.create(source.chat_id, tail)
            except (ProjectNameError, RuntimeError) as exc:
                return str(exc)
            return (
                f"✅ Проект «{created.name}» создан. "
                f"Откройте новый Telegram topic (thread {created.thread_id})."
            )
        if args:
            return "Использование: /projects или /projects new <название>"
        return await self._send_card(self.ui.projects(source), source)

    async def projects_tool(self, params: Mapping[str, Any], **_: Any) -> str:
        """List projects or start the owner's original request in a native topic."""
        action = str(params.get("action") or "list")
        if action == "start":
            try:
                source = self._telegram_source(self.current_request())
                created = await self.projects.start(
                    source.chat_id,
                    source.user_id,
                    str(params.get("name") or ""),
                    str(params.get("task") or ""),
                )
            except (ProjectNameError, RuntimeError, ValueError) as exc:
                return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
            return json.dumps(
                {
                    "ok": True,
                    "started": True,
                    "name": created.name,
                    "thread_id": created.thread_id,
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
        return await self._send_card(await self.today.card(source), source)

    async def tasks_command(self, raw_args: str) -> None | str:
        if (raw_args or "").strip():
            return "Использование: /tasks"
        source = self._telegram_source(self.current_request())
        return await self._send_card(self.ui.personal_tasks(source), source)

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
        if self.calendar is not None:
            calendar_card = self.calendar.callback(str(payload.get("action") or ""), payload)
            if calendar_card is not None:
                return {"plugin": "charline", "card": calendar_card}
        if str(payload.get("action") or "") == "today":
            if hasattr(self._ctx, "spawn_task"):
                self._ctx.spawn_task(
                    self._update_today_card(payload), name="charline:today"
                )
            return {
                "plugin": "charline",
                "card": {"text": "Собираю актуальную сводку…", "buttons": []},
            }
        card = self.ui_callback(str(payload.get("action") or ""), payload)
        return {"plugin": "charline", "card": card}

    async def _update_today_card(self, payload: Mapping[str, Any]) -> None:
        source = self._callback_source(payload)
        card = await self.today.card(source)
        await self.actions.update_card(
            platform="telegram",
            chat_id=str(payload.get("chat_id") or ""),
            message_id=str(payload.get("message_id") or ""),
            text=str(card["text"]),
            buttons=list(card.get("buttons") or []),
            thread_id=str(payload.get("thread_id") or ""),
            owner_user_id=str(payload.get("user_id") or ""),
        )

    def fast_action(self, event: Any, **kwargs: Any) -> dict[str, str] | None:
        if self.calendar is None:
            return None
        return self.calendar.intercept(event, **kwargs)


def register(ctx: Any) -> None:
    plugin = CharlinePlugin(ctx)
    ctx.register_auxiliary_task(
        "calendar_parse",
        display_name="Charline Calendar parser",
        description="Structured parsing for exact Calendar event creation.",
        defaults={"max_tokens": 350, "timeout": 20},
    )
    ctx.register_hook("pre_gateway_dispatch", plugin.capture_request)
    ctx.register_hook("post_auth_pre_agent_dispatch", plugin.fast_action)
    ctx.register_hook("gateway_platform_event", plugin.platform_event)
    ctx.register_command(
        name="charline",
        handler=plugin.charline_command,
        description="Открыть Charline",
    )
    ctx.register_command(
        name="projects",
        handler=plugin.projects_command,
        description="Показать или создать Telegram-проект",
        args_hint="[new <название>]",
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
                "List native Charline Telegram projects or move the owner's original "
                "request into a persistent project topic and start Hermes there. Use "
                "start only when the model judges that durable project context is useful; "
                "ordinary questions and small direct operations stay in the current chat."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "start"]},
                    "name": {"type": "string"},
                    "task": {
                        "type": "string",
                        "description": "The owner's complete original request, without rewriting or loss.",
                    },
                },
                "required": ["action"],
            },
        },
        handler=plugin.projects_tool,
        is_async=True,
    )
