from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

from plugins.charline.calendar import CalendarFastPath
from plugins.charline.calendar_google import CalendarExecutionResult


class FakeState:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


def _event(text="Запиши прогулку завтра в 14 на полтора часа"):
    return SimpleNamespace(text=text, source=SimpleNamespace(
        platform=SimpleNamespace(value="telegram"), chat_id="123", thread_id=None,
        user_id="42", chat_type="dm",
    ))


def _draft(missing=None):
    return {
        "intent": "calendar_create",
        "title": "Прогулка",
        "date": {"type": "relative_day", "offset": 1},
        "time": {"type": "local_time", "value": "14:00"},
        "duration_minutes": None if missing else 90,
        "end_time": None,
        "timezone": None,
        "missing_fields": ["duration_minutes"] if missing else [],
    }


class FakeContext:
    def __init__(self, parsed, *, state=None):
        self.state = state or FakeState()
        self.platform_actions = SimpleNamespace(
            send_card=AsyncMock(return_value={"ok": True, "message_id": "9"}),
            update_card=AsyncMock(return_value={"ok": True, "message_id": "9"}),
            dispatch_agent_turn=AsyncMock(return_value={"ok": True}),
        )
        self.llm = SimpleNamespace(acomplete_structured=AsyncMock(
            return_value=SimpleNamespace(parsed=parsed)
        ))
        self.tasks = []

    def spawn_task(self, coro, *, name=None):
        task = asyncio.create_task(coro, name=name)
        self.tasks.append(task)
        return task


async def _drain(ctx):
    while ctx.tasks:
        tasks, ctx.tasks = ctx.tasks, []
        await asyncio.gather(*tasks)


def _fast(ctx, executor=None):
    return CalendarFastPath(
        ctx,
        executor=executor or SimpleNamespace(execute=AsyncMock(
            return_value=CalendarExecutionResult("completed", "event-1", "https://calendar")
        )),
        now=lambda: datetime(2026, 8, 20, 12, 0, tzinfo=ZoneInfo("Europe/Moscow")),
        timezone_loader=lambda: "Europe/Moscow",
    )


def test_non_candidate_falls_through_without_llm_call():
    ctx = FakeContext(_draft())
    fast = _fast(ctx)
    assert fast.intercept(_event("Расскажи про пятницу")) is None
    ctx.llm.acomplete_structured.assert_not_awaited()


def test_candidate_uses_one_parse_call_and_sends_confirmation_card():
    async def scenario():
        ctx = FakeContext(_draft())
        fast = _fast(ctx)
        assert fast.intercept(_event()) == {"action": "skip", "reason": "charline_calendar_fast_path"}
        await _drain(ctx)
        ctx.llm.acomplete_structured.assert_awaited_once()
        card = ctx.platform_actions.send_card.await_args.kwargs
        assert "21 августа 2026" in card["text"]
        assert "14:00–15:30" in card["text"]
        assert [button["label"] for button in card["buttons"][0]] == ["Подтвердить", "Отмена"]
    asyncio.run(scenario())


def test_missing_duration_asks_directly_without_full_agent_turn():
    async def scenario():
        ctx = FakeContext(_draft(missing=True))
        fast = _fast(ctx)
        fast.intercept(_event())
        await _drain(ctx)
        card = ctx.platform_actions.send_card.await_args.kwargs
        assert "45" in card["text"]
        ctx.platform_actions.dispatch_agent_turn.assert_not_awaited()
        ctx.llm.acomplete_structured.assert_awaited_once()
    asyncio.run(scenario())


def test_duration_reply_completes_direct_preview_without_main_context():
    async def scenario():
        state = FakeState()
        first = FakeContext(_draft(missing=True), state=state)
        fast = _fast(first)

        fast.intercept(_event())
        await _drain(first)

        restarted = FakeContext(_draft(missing=True), state=state)
        fast = _fast(restarted)
        foreign = _event("45 минут")
        foreign.source.user_id = "99"
        assert fast.intercept(foreign) is None
        assert fast.intercept(_event("45 минут")) == {
            "action": "skip",
            "reason": "charline_calendar_fast_path",
        }
        await _drain(restarted)

        preview = restarted.platform_actions.send_card.await_args.kwargs
        assert "14:00" in preview["text"]
        assert "14:45" in preview["text"]
        assert len(preview["buttons"][0]) == 2
        first.platform_actions.dispatch_agent_turn.assert_not_awaited()
        restarted.platform_actions.dispatch_agent_turn.assert_not_awaited()
        first.llm.acomplete_structured.assert_awaited_once()
        restarted.llm.acomplete_structured.assert_not_awaited()

    asyncio.run(scenario())


def test_uncertain_unsupported_or_multiple_actions_fall_back_without_mutation():
    async def scenario(intent):
        draft = _draft()
        draft["intent"] = intent
        ctx = FakeContext(draft)
        executor = SimpleNamespace(execute=AsyncMock())
        fast = _fast(ctx, executor)
        fast.intercept(_event())
        await _drain(ctx)
        ctx.platform_actions.dispatch_agent_turn.assert_awaited_once()
        ctx.platform_actions.send_card.assert_not_awaited()
        executor.execute.assert_not_awaited()

    for intent in ("uncertain", "unsupported", "multiple_actions"):
        asyncio.run(scenario(intent))


def test_confirm_returns_immediately_executes_once_and_updates_same_card():
    async def scenario():
        ctx = FakeContext(_draft())
        executor = SimpleNamespace(execute=AsyncMock(
            return_value=CalendarExecutionResult("completed", "event-1", "https://calendar")
        ))
        fast = _fast(ctx, executor)
        fast.intercept(_event())
        await _drain(ctx)
        action = ctx.platform_actions.send_card.await_args.kwargs["buttons"][0][0]["action"]
        payload = {
            "action": action, "chat_id": "123", "thread_id": "", "user_id": "42", "message_id": "9"
        }
        first = fast.callback(action, payload)
        second = fast.callback(action, payload)
        assert first["text"] == "Записываю событие…"
        assert "уже" in second["text"].lower()
        await _drain(ctx)
        executor.execute.assert_awaited_once()
        updated = ctx.platform_actions.update_card.await_args.kwargs
        assert updated["message_id"] == "9"
        assert "Событие создано" in updated["text"]
    asyncio.run(scenario())


def test_restart_reconciles_executing_write_without_repeating_insert():
    async def scenario():
        ctx = FakeContext(_draft())
        executor = SimpleNamespace(
            execute=AsyncMock(),
            reconcile=AsyncMock(return_value=CalendarExecutionResult(
                "completed", "event-1", "https://calendar"
            )),
        )
        fast = _fast(ctx, executor)
        action_id = fast._store.create(
            owner_user_id="42",
            chat_id="123",
            thread_id="",
            payload={
                "title": "Прогулка",
                "start": "2026-08-21T14:00:00+03:00",
                "end": "2026-08-21T15:30:00+03:00",
                "timezone": "Europe/Moscow",
            },
        )
        fast._store.claim(
            action_id,
            owner_user_id="42",
            chat_id="123",
            thread_id="",
            message_id="9",
        )
        fast._store.mark_external_started(action_id)

        await fast.recover()

        executor.execute.assert_not_awaited()
        executor.reconcile.assert_awaited_once()
        assert fast._store.get(action_id)["status"] == "completed"
        updated = ctx.platform_actions.update_card.await_args.kwargs
        assert updated["message_id"] == "9"
        assert "Событие создано" in updated["text"]

    asyncio.run(scenario())


def test_restart_before_external_call_marks_definite_failure_without_google_call():
    async def scenario():
        ctx = FakeContext(_draft())
        executor = SimpleNamespace(execute=AsyncMock(), reconcile=AsyncMock())
        fast = _fast(ctx, executor)
        action_id = fast._store.create(
            owner_user_id="42", chat_id="123", thread_id="", payload={"title": "Walk"}
        )
        fast._store.claim(
            action_id,
            owner_user_id="42",
            chat_id="123",
            thread_id="",
            message_id="9",
        )

        await fast.recover()

        executor.execute.assert_not_awaited()
        executor.reconcile.assert_not_awaited()
        assert fast._store.get(action_id)["status"] == "failed"

    asyncio.run(scenario())


def test_cancel_creates_nothing_and_expired_or_wrong_owner_cannot_execute():
    async def scenario():
        ctx = FakeContext(_draft())
        executor = SimpleNamespace(execute=AsyncMock())
        fast = _fast(ctx, executor)
        fast.intercept(_event())
        await _drain(ctx)
        buttons = ctx.platform_actions.send_card.await_args.kwargs["buttons"][0]
        confirm, cancel = buttons[0]["action"], buttons[1]["action"]
        wrong = fast.callback(confirm, {
            "chat_id": "123", "thread_id": "", "user_id": "99", "message_id": "9"
        })
        assert "недоступно" in wrong["text"].lower()
        cancelled = fast.callback(cancel, {
            "chat_id": "123", "thread_id": "", "user_id": "42", "message_id": "9"
        })
        assert "отменено" in cancelled["text"].lower()
        await _drain(ctx)
        executor.execute.assert_not_awaited()
    asyncio.run(scenario())
