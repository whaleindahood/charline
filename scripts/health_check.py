"""Read-only health check for the Hermes-native Charline installation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from typing import Callable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.sync_skills import default_hermes_home, is_managed_skill_name

Runner = Callable[[Sequence[str]], tuple[int, str]]
WINDOWS_LAUNCH_FAILURE_CODES = {3221225477, -1073741819}
DIAGNOSTIC_LAUNCH_ATTEMPTS = 3
TEXT_FILE_SUFFIXES = {
    ".json", ".md", ".py", ".ps1", ".sh", ".toml", ".txt",
    ".vbs", ".yaml", ".yml",
}


def _is_transient_windows_launch_failure(completed: subprocess.CompletedProcess[str]) -> bool:
    if completed.returncode in WINDOWS_LAUNCH_FAILURE_CODES:
        return True
    detail = f"{completed.stdout or ''}\n{completed.stderr or ''}".casefold()
    return "uv trampoline failed to spawn python child process" in detail and any(
        marker in detail
        for marker in ("permission denied", "access is denied", "отказано в доступе")
    )


def default_runner(command: Sequence[str]) -> tuple[int, str]:
    completed = None
    for attempt in range(DIAGNOSTIC_LAUNCH_ATTEMPTS):
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
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
            payload = path.read_bytes()
            if path.suffix.lower() in TEXT_FILE_SUFFIXES:
                payload = payload.replace(b"\r\n", b"\n")
            manifest[relative.as_posix()] = sha256(payload).hexdigest()
    return manifest


def _tree_digest(root: Path) -> str:
    digest = sha256()
    for relative, file_hash in _tree_manifest(root).items():
        digest.update(relative.encode("utf-8") + b"\0" + file_hash.encode("ascii"))
    return digest.hexdigest()


def _plugin_state_path(hermes_home: Path, plugin_id: str = "charline") -> Path:
    slug = "".join(
        char if char.isascii() and (char.isalnum() or char in "_-") else "-"
        for char in plugin_id.lower()
    ).strip("-_") or "plugin"
    suffix = sha256(plugin_id.encode("utf-8")).hexdigest()[:8]
    return hermes_home / "plugin-data" / f"agent-plugin-{slug}-{suffix}" / "state.json"


def _loaded_runtime_version(hermes_home: Path) -> dict[str, object]:
    try:
        state = json.loads(_plugin_state_path(hermes_home).read_text(encoding="utf-8"))
        value = state.get("runtime_version") if isinstance(state, dict) else None
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _run_check(runner: Runner, command: Sequence[str]) -> tuple[int, str]:
    try:
        return runner(command)
    except Exception as error:  # Diagnostics must degrade instead of crashing.
        return 1, f"{type(error).__name__}: {error}"


def _is_managed_skill(path: Path) -> bool:
    return (
        is_managed_skill_name(path.name)
        and path.is_dir()
        and (path / "SKILL.md").is_file()
    )


def collect_health(*, project_root: Path, hermes_home: Path, runner: Runner = default_runner) -> dict:
    project_root = Path(project_root)
    hermes_home = Path(hermes_home)
    source_root = project_root / "skills" / "productivity"
    destination_root = hermes_home / "skills" / "productivity"

    source_skills = sorted(
        path
        for path in (source_root.iterdir() if source_root.is_dir() else ())
        if _is_managed_skill(path)
    )
    mismatched = []
    for source in source_skills:
        target = destination_root / source.name
        if not target.is_dir() or _tree_manifest(source) != _tree_manifest(target):
            mismatched.append(source.name)
    source_names = {source.name for source in source_skills}
    active_names = {
        path.name
        for path in (destination_root.iterdir() if destination_root.is_dir() else ())
        if _is_managed_skill(path)
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
    plugin_source = project_root / "plugins" / "charline"
    if plugin_source.is_dir():
        plugin_target = hermes_home / "plugins" / "charline"
        source_hash = _tree_digest(plugin_source)
        target_hash = _tree_digest(plugin_target) if plugin_target.is_dir() else ""
        loaded = _loaded_runtime_version(hermes_home)
        checks["charline_plugin"] = {
            "ok": plugin_target.is_dir()
            and _tree_manifest(plugin_source) == _tree_manifest(plugin_target),
            "detail": {
                "source": str(plugin_source),
                "target": str(plugin_target),
                "source_hash": source_hash,
                "target_hash": target_hash,
            },
        }
        checks["runtime_loaded_plugin"] = {
            "ok": bool(target_hash) and loaded.get("plugin_hash") == target_hash,
            "detail": loaded or "Gateway has not recorded the loaded Charline version",
        }

    repo_code, repo_commit = _run_check(
        runner, ["git", "-C", str(project_root), "rev-parse", "HEAD"]
    )
    hermes_root = hermes_home / "hermes-agent"
    hermes_code, hermes_commit = _run_check(
        runner, ["git", "-C", str(hermes_root), "rev-parse", "HEAD"]
    )
    patch_root = project_root / "patches" / "hermes-agent"
    patch_files = [patch_root / "charline.patch", patch_root / "windows-calendar.patch"]
    checks["runtime_versions"] = {
        "ok": repo_code == 0 and hermes_code == 0 and all(path.is_file() for path in patch_files),
        "detail": {
            "charline_commit": repo_commit.strip(),
            "hermes_commit": hermes_commit.strip(),
            "skills_hash": _tree_digest(source_root) if source_root.is_dir() else "",
            "patch_hashes": {
                path.name: sha256(path.read_bytes()).hexdigest()
                for path in patch_files if path.is_file()
            },
        },
    }
    status = "consistent" if all(check["ok"] for check in checks.values()) else "degraded"
    return {
        "status": status,
        "scope": "repo-profile-consistency",
        "live_runtime_verified": False,
        "checks": checks,
    }


def main() -> int:
    result = collect_health(project_root=PROJECT_ROOT, hermes_home=default_hermes_home())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "consistent" else 1


if __name__ == "__main__":
    raise SystemExit(main())
