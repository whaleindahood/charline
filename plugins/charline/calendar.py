"""Authenticated pre-agent Calendar create fast path."""

from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime
from typing import Any, Mapping

from .calendar_fast_path import (
    DraftIncomplete,
    PendingActionStore,
    is_exact_calendar_candidate,
    resolve_calendar_draft,
)
from .calendar_google import GoogleCalendarExecutor


logger = logging.getLogger(__name__)

CALENDAR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "intent", "title", "date", "time", "duration_minutes",
        "end_time", "timezone", "missing_fields",
    ],
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "calendar_create", "other", "uncertain", "unsupported", "multiple_actions",
            ],
        },
        "title": {"type": ["string", "null"]},
        "date": {"type": ["object", "null"]},
        "time": {"type": ["object", "null"]},
        "duration_minutes": {"type": ["integer", "null"]},
        "end_time": {"type": ["string", "null"]},
        "timezone": {"type": ["string", "null"]},
        "missing_fields": {"type": "array", "items": {"type": "string"}},
    },
}

PARSER_INSTRUCTIONS = """Classify only an explicit request to create one Calendar event.
Return intent=other for availability search, finding a free window, calendar questions,
editing/deleting events, reminders, or ordinary conversation. Return uncertain when the
request can be interpreted in materially different ways, unsupported for recurrence or
explicit attendees/invitations, and multiple_actions for more than one event. Extract the event title and
temporal expression. Never convert a relative date to an absolute date and never assume the
current date. Use one of these date shapes:
{"type":"relative_day","offset":1};
{"type":"relative_weekday","weekday":"friday","direction":"next"};
{"type":"relative_duration","minutes":180};
{"type":"absolute_date","value":"YYYY-MM-DD"} only when the user stated that date.
Use time={"type":"local_time","value":"HH:MM"}. Put an explicit end wall time in
end_time and otherwise duration in duration_minutes. Convert spoken durations to minutes.
Timezone is null unless the user explicitly names one. List every required missing field.
Do not invent a duration, title, date, or time."""

MONTHS_RU = (
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def _default_now() -> datetime:
    from hermes_time import now

    return now()


def _default_timezone() -> str:
    from hermes_time import get_timezone

    zone = get_timezone()
    if zone is None:
        return ""
    return str(getattr(zone, "key", zone))


class CalendarFastPath:
    def __init__(
        self,
        ctx: Any,
        *,
        executor: Any = None,
        now=_default_now,
        timezone_loader=_default_timezone,
    ):
        self._ctx = ctx
        self._actions = ctx.platform_actions
        self._llm = ctx.llm
        self._store = PendingActionStore(ctx.state, now=time.time)
        self._executor = executor or GoogleCalendarExecutor()
        self._now = now
        self._timezone_loader = timezone_loader

    @staticmethod
    def _source(event: Any) -> Any | None:
        source = getattr(event, "source", None)
        platform = getattr(getattr(source, "platform", None), "value", "")
        if (
            platform != "telegram"
            or str(getattr(source, "chat_type", "") or "").lower() not in {"dm", "private"}
            or not getattr(source, "chat_id", None)
            or not getattr(source, "user_id", None)
        ):
            return None
        return source

    def intercept(self, event: Any, **_: Any) -> dict[str, str] | None:
        """Run only from Hermes' post-auth/pre-agent hook."""
        source = self._source(event)
        text = str(getattr(event, "text", "") or "")
        if source is None or text.startswith("/") or not is_exact_calendar_candidate(text):
            return None
        operation_id = secrets.token_hex(4)
        logger.info(
            "calendar_fast_path operation_id=%s milestone=telegram_received", operation_id
        )
        self._ctx.spawn_task(
            self._prepare(text, source, operation_id), name="charline:calendar-parse"
        )
        return {"action": "skip", "reason": "charline_calendar_fast_path"}

    async def _prepare(self, text: str, source: Any, operation_id: str) -> None:
        logger.info(
            "calendar_fast_path operation_id=%s milestone=parser_started", operation_id
        )
        try:
            result = await self._llm.acomplete_structured(
                instructions=PARSER_INSTRUCTIONS,
                input=[{"type": "text", "text": text}],
                json_schema=CALENDAR_SCHEMA,
                schema_name="charline_calendar_draft",
                temperature=0,
                max_tokens=350,
                timeout=20,
                purpose="calendar exact-event parsing",
                task="calendar_parse",
            )
            draft = result.parsed
            logger.info(
                "calendar_fast_path operation_id=%s milestone=parser_finished", operation_id
            )
            if not isinstance(draft, Mapping) or draft.get("intent") != "calendar_create":
                await self._fallback(text, source)
                return
            event = resolve_calendar_draft(
                draft, now=self._now(), profile_timezone=self._timezone_loader()
            )
        except (DraftIncomplete, ValueError, TypeError):
            await self._fallback(text, source)
            return
        except Exception:
            logger.warning("calendar fast parser failed; falling back", exc_info=True)
            await self._fallback(text, source)
            return

        action_id = self._store.create(
            owner_user_id=str(source.user_id),
            chat_id=str(source.chat_id),
            thread_id=str(source.thread_id or ""),
            payload=event.payload(),
        )
        sent = await self._actions.send_card(
            platform="telegram",
            chat_id=str(source.chat_id),
            thread_id=str(source.thread_id or ""),
            owner_user_id=str(source.user_id),
            text=self._preview(event),
            buttons=[[{
                "label": "Подтвердить", "action": f"cal.y.{action_id}",
            }, {
                "label": "Отмена", "action": f"cal.n.{action_id}",
            }]],
        )
        if not sent.get("ok"):
            self._store.cancel(
                action_id,
                owner_user_id=str(source.user_id),
                chat_id=str(source.chat_id),
                thread_id=str(source.thread_id or ""),
            )
            logger.warning("calendar confirmation card failed action_id=%s", action_id)
            return
        logger.info(
            "calendar_fast_path operation_id=%s milestone=confirmation_sent action_id=%s",
            operation_id,
            action_id,
        )

    async def _fallback(self, text: str, source: Any) -> None:
        await self._actions.dispatch_agent_turn(
            platform="telegram",
            chat_id=str(source.chat_id),
            thread_id=str(source.thread_id or ""),
            owner_user_id=str(source.user_id),
            prompt=text,
        )

    @staticmethod
    def _preview(event: Any) -> str:
        day = event.start
        return (
            f"{event.title}\n"
            f"{day.day} {MONTHS_RU[day.month]} {day.year}, "
            f"{day:%H:%M}–{event.end:%H:%M}\n"
            f"{event.timezone}"
        )

    def callback(self, action: str, payload: Mapping[str, Any]) -> dict[str, Any] | None:
        if not (action.startswith("cal.y.") or action.startswith("cal.n.")):
            return None
        action_id = action.rsplit(".", 1)[-1]
        owner = str(payload.get("user_id") or "")
        chat_id = str(payload.get("chat_id") or "")
        thread_id = str(payload.get("thread_id") or "")
        item = self._store.get(action_id)
        if not item or (
            item.get("owner_user_id") != owner
            or item.get("chat_id") != chat_id
            or item.get("thread_id") != thread_id
        ):
            return {"text": "Это действие недоступно.", "buttons": []}
        if action.startswith("cal.n."):
            if self._store.cancel(
                action_id, owner_user_id=owner, chat_id=chat_id, thread_id=thread_id
            ):
                return {"text": "Создание события отменено.", "buttons": []}
            return {"text": "Это действие уже выполнено.", "buttons": []}

        claimed = self._store.claim(
            action_id,
            owner_user_id=owner,
            chat_id=chat_id,
            thread_id=thread_id,
            message_id=str(payload.get("message_id") or ""),
        )
        if claimed is None:
            return {"text": "Это действие уже выполнено или больше не актуально.", "buttons": []}
        logger.info("calendar_fast_path milestone=confirmation_clicked action_id=%s", action_id)
        self._ctx.spawn_task(
            self._execute(
                action_id,
                claimed,
                message_id=str(payload.get("message_id") or ""),
            ),
            name=f"charline:calendar-write:{action_id}",
        )
        return {"text": "Записываю событие…", "buttons": []}

    async def _execute(
        self, action_id: str, item: Mapping[str, Any], *, message_id: str
    ) -> None:
        self._store.mark_external_started(action_id)
        logger.info("calendar_fast_path milestone=google_started action_id=%s", action_id)
        try:
            result = await self._executor.execute(item["payload"])
        except Exception as exc:
            self._store.mark_unknown(action_id, error=str(exc))
            result = None
        logger.info("calendar_fast_path milestone=google_finished action_id=%s", action_id)
        text = self._finish_text(action_id, item, result)
        await self._update_result_card(item, message_id, text)
        logger.info("calendar_fast_path milestone=card_updated action_id=%s", action_id)

    def _finish_text(
        self, action_id: str, item: Mapping[str, Any], result: Any
    ) -> str:
        if result is not None and result.status == "completed":
            self._store.complete(
                action_id, external_resource_id=result.external_resource_id
            )
            link = f"\n{result.html_link}" if result.html_link else ""
            text = f"Событие создано.\n\n{item['payload']['title']}{link}"
        elif result is not None and result.status == "failed":
            self._store.fail(action_id, error=result.detail)
            text = "Событие не создано. Google отклонил операцию."
        else:
            if result is not None:
                self._store.mark_unknown(action_id, error=result.detail)
            text = (
                "Не удалось достоверно определить результат. Повторная запись не "
                "запускалась; проверьте календарь перед новой попыткой."
            )
        return text

    async def _update_result_card(
        self, item: Mapping[str, Any], message_id: str, text: str
    ) -> None:
        if message_id:
            await self._actions.update_card(
                platform="telegram",
                chat_id=str(item["chat_id"]),
                message_id=message_id,
                thread_id=str(item.get("thread_id") or ""),
                owner_user_id=str(item["owner_user_id"]),
                text=text,
                buttons=[],
            )

    async def recover(self) -> None:
        """Reconcile crash-interrupted writes without repeating a mutation."""
        for item in self._store.recoverable():
            action_id = str(item["action_id"])
            if not item.get("external_started_at"):
                self._store.fail(action_id, error="interrupted before Calendar write")
                text = "Событие не создавалось: Gateway остановился до обращения к Google."
            else:
                try:
                    result = await self._executor.reconcile(
                        item["payload"], str(item.get("external_resource_id") or "")
                    )
                except Exception as exc:
                    result = None
                    self._store.mark_unknown(action_id, error=str(exc))
                text = self._finish_text(action_id, item, result)
            await self._update_result_card(item, str(item.get("message_id") or ""), text)
            logger.info(
                "calendar_fast_path milestone=recovery_completed action_id=%s status=%s",
                action_id,
                (self._store.get(action_id) or {}).get("status", "evicted"),
            )
