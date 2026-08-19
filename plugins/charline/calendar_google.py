"""Direct bounded execution through Hermes' existing Google Workspace script."""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping


CommandResult = tuple[int, str, str, bool]
CommandRunner = Callable[[list[str], float], Awaitable[CommandResult]]


@dataclass(frozen=True)
class CalendarExecutionResult:
    status: str
    external_resource_id: str = ""
    html_link: str = ""
    detail: str = ""


async def _run_command(argv: list[str], timeout: float) -> CommandResult:
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return -1, "", "timeout", True
    return (
        int(process.returncode or 0),
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
        False,
    )


def _default_script_path() -> str:
    from hermes_cli.config import get_project_root

    return str(
        get_project_root()
        / "skills"
        / "productivity"
        / "google-workspace"
        / "scripts"
        / "google_api.py"
    )


def _same_instant(left: str, right: str) -> bool:
    try:
        return datetime.fromisoformat(left.replace("Z", "+00:00")) == datetime.fromisoformat(
            right.replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return False


class GoogleCalendarExecutor:
    """One insert and one narrow reconciliation read; never blind-retries writes."""

    def __init__(
        self,
        *,
        command_runner: CommandRunner = _run_command,
        script_path: str | None = None,
        timeout_seconds: float = 20,
    ):
        self._run = command_runner
        self._script = str(script_path or _default_script_path())
        self._timeout = timeout_seconds

    async def execute(self, event: Mapping[str, Any]) -> CalendarExecutionResult:
        if not Path(self._script).is_file() and self._script != "google_api.py":
            return CalendarExecutionResult("failed", detail="Google Workspace script is unavailable")
        create = [
            sys.executable,
            self._script,
            "calendar",
            "create",
            "--summary",
            str(event["title"]),
            "--start",
            str(event["start"]),
            "--end",
            str(event["end"]),
        ]
        code, stdout, stderr, timed_out = await self._run(create, self._timeout)
        created_id = ""
        if code == 0 and not timed_out:
            try:
                created = json.loads(stdout)
                created_id = str(created.get("id") or "")
            except (TypeError, ValueError):
                timed_out = True  # outcome cannot be proven from the response
        elif not timed_out:
            return CalendarExecutionResult("failed", detail=(stderr or stdout)[:512])

        reconciled = await self._reconcile(event, created_id)
        if reconciled is not None:
            return CalendarExecutionResult(
                "completed",
                external_resource_id=str(reconciled.get("id") or created_id),
                html_link=str(reconciled.get("htmlLink") or ""),
            )
        if created_id:
            return CalendarExecutionResult(
                "unknown", external_resource_id=created_id,
                detail="event was inserted but read-back did not verify it",
            )
        return CalendarExecutionResult(
            "unknown", detail=(stderr or "Calendar write timed out")[:512]
        )

    async def _reconcile(
        self, event: Mapping[str, Any], expected_id: str
    ) -> Mapping[str, Any] | None:
        start = datetime.fromisoformat(str(event["start"]).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(event["end"]).replace("Z", "+00:00"))
        command = [
            sys.executable,
            self._script,
            "calendar",
            "list",
            "--start",
            (start - timedelta(minutes=1)).isoformat(),
            "--end",
            (end + timedelta(minutes=1)).isoformat(),
            "--max",
            "20",
        ]
        code, stdout, _stderr, timed_out = await self._run(command, self._timeout)
        if code != 0 or timed_out:
            return None
        try:
            items = json.loads(stdout)
        except (TypeError, ValueError):
            return None
        if not isinstance(items, list):
            return None
        for item in items:
            if not isinstance(item, Mapping):
                continue
            if expected_id and str(item.get("id") or "") != expected_id:
                continue
            if (
                str(item.get("summary") or "") == str(event["title"])
                and _same_instant(str(item.get("start") or ""), str(event["start"]))
                and _same_instant(str(item.get("end") or ""), str(event["end"]))
            ):
                return item
        return None


class GoogleCalendarReader:
    """Bounded read helper used by Today; Google remains source of truth."""

    def __init__(
        self,
        *,
        command_runner: CommandRunner = _run_command,
        script_path: str | None = None,
        timeout_seconds: float = 20,
    ):
        self._run = command_runner
        self._script = str(script_path or _default_script_path())
        self._timeout = timeout_seconds

    async def list_between(self, start: datetime, end: datetime) -> list[dict[str, Any]] | None:
        command = [
            sys.executable, self._script, "calendar", "list",
            "--start", start.isoformat(), "--end", end.isoformat(), "--max", "20",
        ]
        code, stdout, _stderr, timed_out = await self._run(command, self._timeout)
        if code != 0 or timed_out:
            return None
        try:
            items = json.loads(stdout)
        except (TypeError, ValueError):
            return None
        return [dict(item) for item in items if isinstance(item, Mapping)] if isinstance(items, list) else None
