"""Plan calendar availability from normalized JSON without API access."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from charline.availability import AvailabilityValidationError, plan_availability


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="-", help="JSON path or - for stdin")
    args = parser.parse_args()
    try:
        if args.input == "-":
            request = json.load(sys.stdin)
        else:
            request = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = plan_availability(request)
    except (OSError, json.JSONDecodeError, AvailabilityValidationError, ValueError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "ok", "data": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
