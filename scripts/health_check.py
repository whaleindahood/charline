"""Read-only health check for the Hermes-native Charline installation."""

from __future__ import annotations

import json
import os
import subprocess
from hashlib import sha256
from pathlib import Path
from typing import Callable, Sequence

Runner = Callable[[Sequence[str]], tuple[int, str]]


def default_runner(command: Sequence[str]) -> tuple[int, str]:
    completed = None
    for attempt in range(2):
        completed = subprocess.run(
            command,
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
    output = (completed.stdout or completed.stderr).strip()
    return completed.returncode, output


def _tree_manifest(root: Path) -> dict[str, str]:
    """Return hashes for managed files without reading runtime temp artifacts."""
    manifest: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part == "__pycache__" for part in relative.parts):
            continue
        if path.name.startswith(".hermes-tmp.") or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            manifest[relative.as_posix()] = f"link:{os.readlink(path)}"
        elif path.is_file():
            manifest[relative.as_posix()] = sha256(path.read_bytes()).hexdigest()
    return manifest


def _run_check(runner: Runner, command: Sequence[str]) -> tuple[int, str]:
    try:
        return runner(command)
    except Exception as error:  # Diagnostics must degrade instead of crashing.
        return 1, f"{type(error).__name__}: {error}"


def collect_health(*, project_root: Path, hermes_home: Path, runner: Runner = default_runner) -> dict:
    project_root = Path(project_root)
    hermes_home = Path(hermes_home)
    source_root = project_root / "skills" / "productivity"
    destination_root = hermes_home / "skills" / "productivity"

    source_skills = sorted(
        path for path in source_root.glob("charline-*")
        if path.is_dir() and (path / "SKILL.md").is_file()
    )
    mismatched = []
    for source in source_skills:
        target = destination_root / source.name
        if not target.is_dir() or _tree_manifest(source) != _tree_manifest(target):
            mismatched.append(source.name)
    source_names = {source.name for source in source_skills}
    active_names = {
        path.name
        for path in destination_root.glob("charline-*")
        if path.is_dir() and (path / "SKILL.md").is_file()
    }
    extra = sorted(active_names - source_names)

    version_code, version_output = _run_check(runner, ["hermes", "--version"])
    config_code, config_output = _run_check(runner, ["hermes", "config", "check"])

    checks = {
        "independent_git": {"ok": (project_root / ".git").is_dir(), "detail": str(project_root / ".git")},
        "managed_skills": {
            "ok": len(source_skills) >= 1 and not mismatched and not extra,
            "detail": {
                "count": len(source_skills),
                "mismatched": mismatched,
                "extra": extra,
            },
        },
        "google_oauth_files": {
            "ok": (hermes_home / "google_token.json").is_file() and (hermes_home / "google_client_secret.json").is_file(),
            "detail": "presence checked; contents not read",
        },
        "hermes_version": {"ok": version_code == 0, "detail": version_output.splitlines()[0] if version_output else "no output"},
        "hermes_config": {"ok": config_code == 0, "detail": "valid" if config_code == 0 else config_output[-500:]},
    }
    status = "consistent" if all(check["ok"] for check in checks.values()) else "degraded"
    return {
        "status": status,
        "scope": "repo-profile-consistency",
        "live_runtime_verified": False,
        "checks": checks,
    }


def default_hermes_home() -> Path:
    configured = os.environ.get("HERMES_HOME")
    if configured:
        return Path(configured)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "hermes"
    return Path.home() / ".hermes"


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    result = collect_health(project_root=project_root, hermes_home=default_hermes_home())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "consistent" else 1


if __name__ == "__main__":
    raise SystemExit(main())
