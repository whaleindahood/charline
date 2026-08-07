#!/usr/bin/env python3
"""Build a deterministic Hermes reminder draft from JSON input."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from charline.reminders import build_reminder_draft  # noqa: E402


def main() -> int:
    payload = json.load(sys.stdin)
    now_value = payload.pop("now", None)
    now = (
        datetime.fromisoformat(str(now_value).replace("Z", "+00:00"))
        if now_value
        else datetime.now(timezone.utc)
    )
    print(
        json.dumps(
            build_reminder_draft(now=now, **payload),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
