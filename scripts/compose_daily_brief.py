"""Compose a deterministic read-only daily brief from normalized JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from charline.briefing import BriefingValidationError, compose_daily_brief


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="-", help="JSON path or - for stdin")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()

    try:
        if args.input == "-":
            snapshot = json.load(sys.stdin)
        else:
            snapshot = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = compose_daily_brief(snapshot)
    except (OSError, json.JSONDecodeError, BriefingValidationError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False))
        return 1

    if args.format == "markdown":
        print(result["markdown"])
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
