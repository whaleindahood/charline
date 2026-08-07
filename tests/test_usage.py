import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charline.usage import UsageBudget, summarize_usage
from scripts.usage_report import collect_usage


class UsagePolicyTests(unittest.TestCase):
    def test_flags_large_context_and_excess_parallel_subagents(self):
        rows = [
            {
                "id": "session-1",
                "source": "telegram",
                "message_count": 130,
                "api_call_count": 320,
                "input_tokens": 300_000,
                "output_tokens": 10_000,
                "cache_read_tokens": 6_000_000,
            }
        ]
        report = summarize_usage(rows, active_subagents=3, budget=UsageBudget())
        self.assertIn("rotate_session:session-1:messages", report["alerts"])
        self.assertIn("rotate_session:session-1:cache_read_tokens", report["alerts"])
        self.assertIn("delegation_limit:3>2", report["alerts"])

    def test_keeps_fresh_and_cached_tokens_separate(self):
        rows = [
            {
                "id": "s1",
                "source": "telegram",
                "message_count": 2,
                "api_call_count": 1,
                "input_tokens": 100,
                "output_tokens": 20,
                "cache_read_tokens": 900,
            },
            {
                "id": "s2",
                "source": "subagent",
                "message_count": 3,
                "api_call_count": 2,
                "input_tokens": 200,
                "output_tokens": 30,
                "cache_read_tokens": 800,
            },
        ]
        report = summarize_usage(rows, active_subagents=0, budget=UsageBudget())
        self.assertEqual(report["totals"]["input_tokens"], 300)
        self.assertEqual(report["totals"]["cache_read_tokens"], 1700)
        self.assertEqual(report["by_source"]["subagent"]["api_call_count"], 2)

    def test_collect_usage_reads_runtime_db_without_message_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "state.db"
            connection = sqlite3.connect(database)
            connection.execute(
                """CREATE TABLE sessions (
                    id TEXT, source TEXT, started_at REAL, ended_at REAL,
                    message_count INTEGER, api_call_count INTEGER,
                    input_tokens INTEGER, output_tokens INTEGER,
                    cache_read_tokens INTEGER
                )"""
            )
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("s1", "subagent", 1000.0, None, 4, 3, 100, 20, 500),
            )
            connection.commit()
            connection.close()

            report = collect_usage(database, cutoff=0)
            self.assertEqual(report["active_subagents"], 1)
            self.assertEqual(report["totals"]["input_tokens"], 100)


if __name__ == "__main__":
    unittest.main()
