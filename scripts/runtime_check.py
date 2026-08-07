#!/usr/bin/env python3
"""Read-only verification of the local Hermes runtime.

This script deliberately checks process/config state without starting services or
changing Hermes configuration.  The optional Google check is explicit because
the upstream helper may refresh an OAuth token while validating credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence


CommandRunner = Callable[[Sequence[str]], tuple[int, str]]
SUPPORTED_HERMES_VERSION = "Hermes Agent v0.19.0"


def default_hermes_home() -> Path:
    configured = os.environ.get("HERMES_HOME")
    if configured:
        return Path(configured)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "hermes"
    return Path.home() / ".hermes"


def default_runner(command: Sequence[str]) -> tuple[int, str]:
    """Run one bounded diagnostic command and combine stdout/stderr."""

    completed = None
    for attempt in range(2):
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        if completed.returncode not in {3221225477, -1073741819} or attempt == 1:
            break
    assert completed is not None
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    return completed.returncode, output.strip()


def _run(runner: CommandRunner, command: Sequence[str]) -> dict[str, object]:
    try:
        code, output = runner(command)
        return {"returncode": code, "detail": output[-4000:], "_raw": output}
    except Exception as exc:  # diagnostics must report launcher failures, not crash
        detail = f"{type(exc).__name__}: {exc}"
        return {"returncode": None, "detail": detail, "_raw": detail}


def _public(result: dict[str, object]) -> dict[str, object]:
    return {"returncode": result["returncode"], "detail": result["detail"]}


def _python_for_google(hermes_home: Path) -> str:
    candidates = (
        hermes_home / "hermes-agent" / "venv" / "Scripts" / "python.exe",
        hermes_home / "hermes-agent" / "venv" / "bin" / "python",
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def collect_runtime(
    hermes_home: Path,
    runner: CommandRunner = default_runner,
    *,
    check_live_google: bool = False,
) -> dict[str, object]:
    """Collect bounded readiness evidence for the supported Hermes runtime."""

    hermes_home = Path(hermes_home)
    raw_version = _run(runner, ["hermes", "--version"])
    raw_config = _run(runner, ["hermes", "config", "check"])
    raw_doctor = _run(runner, ["hermes", "doctor"])
    raw_gateway = _run(runner, ["hermes", "gateway", "status"])

    version_text = str(raw_version["_raw"])
    config_text = str(raw_config["_raw"])
    doctor_text = str(raw_doctor["_raw"])
    gateway_text = str(raw_gateway["_raw"])
    doctor_lower = doctor_text.casefold()
    doctor_blockers = []
    if "wal-reset" in doctor_lower or "wal reset" in doctor_lower:
        doctor_blockers.append("sqlite-wal-reset")
    pid_match = re.search(r"PID\(s\):\s*([0-9,\s]+)", gateway_text, re.IGNORECASE)
    pids = []
    if pid_match:
        pids = sorted(
            {
                int(value)
                for value in re.findall(r"\d+", pid_match.group(1))
                if int(value) > 0
            }
        )

    checks: dict[str, dict[str, object]] = {
        "hermes_version": {
            **_public(raw_version),
            "ok": raw_version["returncode"] == 0
            and SUPPORTED_HERMES_VERSION in version_text,
            "expected": SUPPORTED_HERMES_VERSION,
        },
        "config": {
            **_public(raw_config),
            "ok": raw_config["returncode"] == 0
            and "TELEGRAM_BOT_TOKEN" in config_text
            and "TELEGRAM_ALLOWED_USERS" in config_text,
        },
        "doctor": {
            **_public(raw_doctor),
            "ok": raw_doctor["returncode"] == 0 and not doctor_blockers,
            "blocking_findings": doctor_blockers,
        },
        "single_gateway": {
            **_public(raw_gateway),
            "ok": raw_gateway["returncode"] == 0
            and "running" in gateway_text.lower()
            and len(pids) == 1,
            "pids": pids,
        },
    }

    google_setup = (
        hermes_home
        / "skills"
        / "productivity"
        / "google-workspace"
        / "scripts"
        / "setup.py"
    )
    if check_live_google:
        if google_setup.is_file():
            raw_google = _run(
                runner,
                [_python_for_google(hermes_home), str(google_setup), "--check-live"],
            )
            checks["google_live"] = {
                **_public(raw_google),
                "ok": raw_google["returncode"] == 0,
            }
        else:
            checks["google_live"] = {
                "returncode": None,
                "detail": f"setup helper not found: {google_setup}",
                "ok": False,
            }
    else:
        checks["google_live"] = {
            "returncode": None,
            "detail": "not requested; pass --live-google for an authenticated read",
            "ok": False,
        }

    live_runtime_verified = check_live_google and all(
        bool(check["ok"]) for check in checks.values()
    )
    return {
        "schema_version": 1,
        "status": "ready" if live_runtime_verified else "degraded",
        "live_runtime_verified": live_runtime_verified,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hermes-home",
        type=Path,
        default=default_hermes_home(),
        help="Hermes data directory (default: HERMES_HOME or platform data directory)",
    )
    parser.add_argument(
        "--live-google",
        action="store_true",
        help="Run the installed Google Workspace authenticated read check",
    )
    args = parser.parse_args()
    report = collect_runtime(args.hermes_home, check_live_google=args.live_google)
    # ASCII escaping keeps diagnostics printable in legacy Windows code pages.
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["live_runtime_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
