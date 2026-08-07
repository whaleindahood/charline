#!/usr/bin/env python3
"""Validate and normalize a JSON research evidence pack."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from charline.research import normalize_evidence  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path)
    args = parser.parse_args()
    raw = args.path.read_text(encoding="utf-8") if args.path else sys.stdin.read()
    payload = json.loads(raw)
    observed = payload.get("observed_at")
    observed_at = (
        datetime.fromisoformat(str(observed).replace("Z", "+00:00"))
        if observed
        else datetime.now(timezone.utc)
    )
    result = normalize_evidence(payload.get("findings", []), observed_at=observed_at)
    print(json.dumps({"findings": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

