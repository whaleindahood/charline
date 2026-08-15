#!/usr/bin/env python3
"""Read-only verification of the local Hermes runtime.

This script deliberately checks process/config state without starting services or
changing Hermes configuration.  The optional Google check is explicit because
the upstream helper may refresh an OAuth token while validating credentials.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.sync_skills import default_hermes_home


CommandRunner = Callable[[Sequence[str]], tuple[int, str]]
WINDOWS_LAUNCH_FAILURE_CODES = {3221225477, -1073741819}
DIAGNOSTIC_LAUNCH_ATTEMPTS = 3
SUPPORTED_HERMES_VERSIONS = (
    "Hermes Agent v0.19.0",
    "Hermes Agent v0.20.0",
)


def _is_transient_windows_launch_failure(completed: subprocess.CompletedProcess[str]) -> bool:
    if completed.returncode in WINDOWS_LAUNCH_FAILURE_CODES:
        return True
    detail = f"{completed.stdout or ''}\n{completed.stderr or ''}".casefold()
    return "uv trampoline failed to spawn python child process" in detail and any(
        marker in detail
        for marker in ("permission denied", "access is denied", "отказано в доступе")
    )


def default_runner(command: Sequence[str]) -> tuple[int, str]:
    """Run one bounded diagnostic command and combine stdout/stderr."""

    timeout = 90 if tuple(map(str, command)) == ("hermes", "doctor") else 30
    completed = None
    for attempt in range(DIAGNOSTIC_LAUNCH_ATTEMPTS):
        try:
            completed = subprocess.run(
                list(command),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except PermissionError:
            if attempt == DIAGNOSTIC_LAUNCH_ATTEMPTS - 1:
                raise
            continue
        if (
            not _is_transient_windows_launch_failure(completed)
            or attempt == DIAGNOSTIC_LAUNCH_ATTEMPTS - 1
        ):
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


def _configured(output: str, name: str) -> bool:
    return re.search(rf"[✓✔]\s+{re.escape(name)}\b", output) is not None


def _google_live_command(hermes_home: Path, setup_path: Path) -> list[str]:
    venv = hermes_home / "hermes-agent" / "venv"
    config = venv / "pyvenv.cfg"
    site_packages = venv / "Lib" / "site-packages"
    if config.is_file() and site_packages.is_dir():
        try:
            home_line = next(
                line
                for line in config.read_text(encoding="utf-8").splitlines()
                if line.casefold().startswith("home =")
            )
            base_home = Path(home_line.split("=", 1)[1].strip())
            base_candidates = (base_home / "python.exe", base_home / "bin" / "python")
            base_python = next(path for path in base_candidates if path.is_file())
            code = (
                "import runpy,sys;"
                f"sys.path.insert(0,{str(site_packages)!r});"
                f"sys.argv=[{str(setup_path)!r},'--check-live'];"
                f"runpy.run_path({str(setup_path)!r},run_name='__main__')"
            )
            return [str(base_python), "-c", code]
        except (OSError, StopIteration, ValueError):
            pass

    candidates = (
        venv / "Scripts" / "python.exe",
        venv / "bin" / "python",
    )
    for candidate in candidates:
        if candidate.is_file():
            return [str(candidate), str(setup_path), "--check-live"]
    return [sys.executable, str(setup_path), "--check-live"]


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
    config_ok = (
        raw_config["returncode"] == 0
        and _configured(config_text, "TELEGRAM_BOT_TOKEN")
        and _configured(config_text, "TELEGRAM_ALLOWED_USERS")
    )
    pid_match = re.search(
        r"PID(?:\(s\))?:\s*([0-9,\s]+)",
        gateway_text,
        re.IGNORECASE,
    )
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
            and any(version in version_text for version in SUPPORTED_HERMES_VERSIONS),
            "expected": list(SUPPORTED_HERMES_VERSIONS),
        },
        "config": {
            "returncode": raw_config["returncode"],
            "detail": (
                "valid; Telegram bot token and allowlist configured"
                if config_ok
                else str(raw_config["detail"])
            ),
            "ok": config_ok,
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
                _google_live_command(hermes_home, google_setup),
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
