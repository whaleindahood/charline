"""Read Hermes-owned usage counters without creating another usage store."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from charline.usage import UsageBudget, summarize_usage
from scripts.health_check import default_hermes_home


def collect_usage(database: Path, *, cutoff: float) -> dict[str, object]:
    database = Path(database)
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = [
            dict(row)
            for row in connection.execute(
                """SELECT id, source, message_count, api_call_count,
                          input_tokens, output_tokens, cache_read_tokens
                   FROM sessions
                   WHERE started_at >= ?
                   ORDER BY started_at""",
                (cutoff,),
            )
        ]
        active_subagents = connection.execute(
            """SELECT COUNT(*) FROM sessions
               WHERE source = 'subagent' AND ended_at IS NULL"""
        ).fetchone()[0]
    finally:
        connection.close()
    return summarize_usage(
        rows,
        active_subagents=int(active_subagents),
        budget=UsageBudget(),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    if args.days <= 0:
        parser.error("--days must be positive")
    database = args.database or (default_hermes_home() / "state.db")
    try:
        report = collect_usage(database, cutoff=time.time() - args.days * 86400)
    except (OSError, sqlite3.Error, ValueError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False))
        return 1
    report["days"] = args.days
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
