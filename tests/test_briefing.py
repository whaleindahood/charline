import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charline.briefing import BriefingValidationError, compose_daily_brief


class DailyBriefingTests(unittest.TestCase):
    def base_snapshot(self):
        return {
            "generated_at": "2026-08-07T09:00:00+03:00",
            "timezone": "Europe/Moscow",
            "sections": [],
        }

    def test_orders_sections_and_deduplicates_items_deterministically(self):
        snapshot = self.base_snapshot()
        snapshot["sections"] = [
            {
                "name": "gmail",
                "status": "ok",
                "observed_at": "2026-08-07T08:59:00+03:00",
                "items": [
                    {"handle": "m2", "title": "Later", "timestamp": "2026-08-07T08:00:00+03:00"},
                    {"handle": "m1", "title": "Earlier", "timestamp": "2026-08-07T07:00:00+03:00"},
                    {"handle": "m1", "title": "Duplicate", "timestamp": "2026-08-07T07:00:00+03:00"},
                ],
            },
            {
                "name": "calendar",
                "status": "empty",
                "observed_at": "2026-08-07T08:58:00+03:00",
                "items": [],
            },
        ]
        result = compose_daily_brief(snapshot)
        self.assertEqual([section["name"] for section in result["sections"]], ["calendar", "gmail"])
        self.assertEqual([item["handle"] for item in result["sections"][1]["items"]], ["m1", "m2"])

    def test_partial_failure_does_not_hide_healthy_sections(self):
        snapshot = self.base_snapshot()
        snapshot["sections"] = [
            {
                "name": "calendar",
                "status": "ok",
                "observed_at": "2026-08-07T08:58:00+03:00",
                "items": [{"handle": "e1", "title": "Standup", "start": "2026-08-07T10:00:00+03:00", "end": "2026-08-07T10:30:00+03:00"}],
            },
            {
                "name": "gmail",
                "status": "unavailable",
                "observed_at": "2026-08-07T08:59:00+03:00",
                "error_code": "AUTH_EXPIRED",
                "items": [],
            },
        ]
        result = compose_daily_brief(snapshot)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["sections"][0]["items"][0]["title"], "Standup")
        self.assertIn("source_unavailable:gmail:AUTH_EXPIRED", result["alerts"])

    def test_detects_calendar_conflict_and_overdue_reminder(self):
        snapshot = self.base_snapshot()
        snapshot["sections"] = [
            {
                "name": "calendar",
                "status": "ok",
                "observed_at": "2026-08-07T08:58:00+03:00",
                "items": [
                    {"handle": "e1", "title": "A", "start": "2026-08-07T10:00:00+03:00", "end": "2026-08-07T11:00:00+03:00"},
                    {"handle": "e2", "title": "B", "start": "2026-08-07T10:30:00+03:00", "end": "2026-08-07T11:30:00+03:00"},
                ],
            },
            {
                "name": "reminders",
                "status": "ok",
                "observed_at": "2026-08-07T08:58:00+03:00",
                "items": [{"handle": "r1", "title": "Pay invoice", "due": "2026-08-07T08:00:00+03:00", "done": False}],
            },
        ]
        result = compose_daily_brief(snapshot)
        self.assertIn("calendar_conflict:e1:e2", result["alerts"])
        self.assertIn("overdue_reminder:r1", result["alerts"])

    def test_markdown_is_attention_first_and_names_source_gaps(self):
        snapshot = self.base_snapshot()
        snapshot["sections"] = [
            {
                "name": "calendar",
                "status": "ok",
                "observed_at": "2026-08-07T08:58:00+03:00",
                "items": [
                    {"handle": "e1", "title": "Созвон с Анной", "start": "2026-08-07T10:00:00+03:00", "end": "2026-08-07T11:00:00+03:00"},
                    {"handle": "e2", "title": "Демо", "start": "2026-08-07T10:30:00+03:00", "end": "2026-08-07T11:30:00+03:00"},
                ],
            },
            {
                "name": "reminders",
                "status": "ok",
                "observed_at": "2026-08-07T08:58:00+03:00",
                "items": [{"handle": "r1", "title": "Оплатить счёт", "due": "2026-08-07T08:00:00+03:00", "done": False}],
            },
            {
                "name": "gmail",
                "status": "unavailable",
                "observed_at": "2026-08-07T08:59:00+03:00",
                "error_code": "AUTH_EXPIRED",
                "items": [],
            },
        ]

        markdown = compose_daily_brief(snapshot)["markdown"]

        self.assertTrue(markdown.startswith("# Сегодня"))
        self.assertIn("## Требует внимания", markdown)
        self.assertIn("Конфликт в календаре: Созвон с Анной ↔ Демо [e1, e2]", markdown)
        self.assertIn("Просрочено: Оплатить счёт [r1]", markdown)
        self.assertIn("Не удалось проверить: Почта", markdown)
        self.assertIn("Проверено: 09:00 · Europe/Moscow", markdown)
        self.assertNotIn("source_unavailable", markdown)
        self.assertNotIn("Status:", markdown)

    def test_markdown_limits_each_section_and_reports_hidden_count(self):
        snapshot = self.base_snapshot()
        snapshot["sections"] = [{
            "name": "gmail",
            "status": "ok",
            "observed_at": "2026-08-07T08:59:00+03:00",
            "items": [
                {"handle": f"m{index}", "title": f"Письмо {index}", "timestamp": f"2026-08-07T0{index}:00:00+03:00"}
                for index in range(1, 5)
            ],
        }]

        markdown = compose_daily_brief(snapshot)["markdown"]

        self.assertIn("### Почта", markdown)
        self.assertIn("Письмо 1 [m1]", markdown)
        self.assertIn("Письмо 3 [m3]", markdown)
        self.assertNotIn("Письмо 4 [m4]", markdown)
        self.assertIn("Ещё: 1", markdown)

    def test_empty_markdown_has_one_honest_message(self):
        snapshot = self.base_snapshot()
        snapshot["sections"] = [{
            "name": "calendar",
            "status": "empty",
            "observed_at": "2026-08-07T08:59:00+03:00",
            "items": [],
        }]

        markdown = compose_daily_brief(snapshot)["markdown"]

        self.assertIn("На сегодня ничего не требует внимания.", markdown)
        self.assertNotIn("No items", markdown)

    def test_research_item_requires_source_url(self):
        snapshot = self.base_snapshot()
        snapshot["sections"] = [
            {
                "name": "research",
                "status": "ok",
                "observed_at": "2026-08-07T08:58:00+03:00",
                "items": [{"handle": "finding-1", "title": "Claim"}],
            }
        ]
        with self.assertRaisesRegex(BriefingValidationError, "research.*url"):
            compose_daily_brief(snapshot)

    def test_research_item_requires_absolute_url_with_host(self):
        snapshot = self.base_snapshot()
        snapshot["sections"] = [
            {
                "name": "research",
                "status": "ok",
                "observed_at": "2026-08-07T08:58:00+03:00",
                "items": [{"handle": "finding-1", "title": "Claim", "url": "http://"}],
            }
        ]
        with self.assertRaisesRegex(BriefingValidationError, "research.*url"):
            compose_daily_brief(snapshot)

    def test_research_item_rejects_malformed_or_whitespace_host(self):
        for url in ("http://[", "https://bad host/path"):
            with self.subTest(url=url):
                snapshot = self.base_snapshot()
                snapshot["sections"] = [
                    {
                        "name": "research",
                        "status": "ok",
                        "observed_at": "2026-08-07T08:58:00+03:00",
                        "items": [
                            {"handle": "finding-1", "title": "Claim", "url": url}
                        ],
                    }
                ]
                with self.assertRaisesRegex(BriefingValidationError, "research.*url"):
                    compose_daily_brief(snapshot)

    def test_rejects_naive_timestamps(self):
        snapshot = self.base_snapshot()
        snapshot["generated_at"] = "2026-08-07T09:00:00"
        with self.assertRaisesRegex(BriefingValidationError, "timezone-aware"):
            compose_daily_brief(snapshot)


if __name__ == "__main__":
    unittest.main()
