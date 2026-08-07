"""Run deterministic Charline policy traces and emit a JSON report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evals.runner import evaluate_suite


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=PROJECT_ROOT / "evals" / "v1_scenarios.json",
    )
    parser.add_argument(
        "--traces",
        type=Path,
        default=PROJECT_ROOT / "evals" / "reference_traces.json",
    )
    args = parser.parse_args()

    scenarios = json.loads(args.scenarios.read_text(encoding="utf-8"))
    traces = json.loads(args.traces.read_text(encoding="utf-8"))
    report = evaluate_suite(scenarios, traces)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
