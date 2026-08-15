from datetime import datetime, timezone

import pytest

from charline.reminders import ReminderError, build_reminder_draft


NOW = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)


def test_one_time_reminder_is_self_contained_and_stable():
    draft = build_reminder_draft(
        message="Позвонить врачу",
        schedule="2026-08-08T09:00:00+03:00",
        schedule_type="once",
        timezone_name="Europe/Moscow",
        destination="main-telegram-chat",
        now=NOW,
    )

    assert draft["operation"] == "hermes.cron.create"
    assert draft["delivery"]["destination"] == "main-telegram-chat"
    assert draft["idempotency_key"]
    assert "Позвонить врачу" in draft["job_prompt"]
    assert "idempotency" in draft["job_prompt"].lower()


def test_past_one_time_reminder_is_rejected():
    with pytest.raises(ReminderError, match="future"):
        build_reminder_draft(
            message="Too late",
            schedule="2026-08-07T10:00:00+00:00",
            schedule_type="once",
            timezone_name="UTC",
            destination="main",
            now=NOW,
        )


def test_cron_requires_five_fields_and_valid_timezone():
    with pytest.raises(ReminderError, match="five fields"):
        build_reminder_draft(
            message="Brief",
            schedule="0 8 * *",
            schedule_type="cron",
            timezone_name="Europe/Moscow",
            destination="main",
            now=NOW,
        )


def test_cron_rejects_out_of_range_expression():
    with pytest.raises(ReminderError, match="cron expression"):
        build_reminder_draft(
            message="Brief",
            schedule="99 99 99 99 99",
            schedule_type="cron",
            timezone_name="Europe/Moscow",
            destination="main",
            now=NOW,
        )
    with pytest.raises(ReminderError, match="timezone"):
        build_reminder_draft(
            message="Brief",
            schedule="0 8 * * *",
            schedule_type="cron",
            timezone_name="Mars/Olympus",
            destination="main",
            now=NOW,
        )
