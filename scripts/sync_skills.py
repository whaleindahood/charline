"""Install version-controlled Charline skills into an active Hermes home."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path


COPY_IGNORE = shutil.ignore_patterns(".hermes-tmp.*", "__pycache__", "*.pyc")


def _paths_overlap(left: Path, right: Path) -> bool:
    left = left.resolve(strict=False)
    right = right.resolve(strict=False)
    return left == right or left in right.parents or right in left.parents


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _reject_links(root: Path) -> None:
    if _is_link_or_reparse(root):
        raise ValueError(f"link or reparse point is not allowed: {root}")
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in [*directories, *files]:
            path = current_path / name
            if _is_link_or_reparse(path):
                raise ValueError(f"link or reparse point is not allowed: {path}")


def _acquire_lock(lock_path: Path) -> None:
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError("Charline skill sync is already in progress") from error
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
    finally:
        os.close(descriptor)


def _tree_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part == "__pycache__" for part in relative.parts):
            continue
        if path.name.startswith(".hermes-tmp.") or path.suffix == ".pyc":
            continue
        if path.is_file() and not _is_link_or_reparse(path):
            hashes[relative.as_posix()] = sha256(path.read_bytes()).hexdigest()
    return hashes


def sync_skills(
    *,
    source_root: Path,
    hermes_home: Path,
    backup_root: Path,
    activate=lambda staging, target: staging.replace(target),
) -> list[str]:
    """Back up and replace the complete managed skill set transactionally."""
    source_root = Path(source_root)
    hermes_home = Path(hermes_home)
    backup_root = Path(backup_root)
    if not source_root.is_dir():
        raise FileNotFoundError(f"skill source not found: {source_root}")

    destination_root = hermes_home / "skills" / "productivity"
    for left, right in (
        (source_root, backup_root),
        (source_root, destination_root),
        (backup_root, destination_root),
    ):
        if _paths_overlap(left, right):
            raise ValueError(f"managed paths overlap: {left} and {right}")

    sources = [
        path for path in sorted(source_root.iterdir(), key=lambda path: path.name)
        if path.is_dir()
        and path.name.startswith("charline-")
        and (path / "SKILL.md").is_file()
    ]
    if not sources:
        raise RuntimeError("no managed Charline skills found")
    for source in sources:
        _reject_links(source)

    destination_root.mkdir(parents=True, exist_ok=True)
    if _is_link_or_reparse(destination_root):
        raise ValueError(f"link or reparse point is not allowed: {destination_root}")
    for source in sources:
        target = destination_root / source.name
        if _is_link_or_reparse(target):
            raise ValueError(f"link or reparse point is not allowed: {target}")

    lock_path = destination_root / ".charline-sync.lock"
    _acquire_lock(lock_path)
    work_root = destination_root / ".charline-sync-work"
    try:
        manifest_path = backup_root / "manifest.json"
        if manifest_path.exists() or _is_link_or_reparse(manifest_path):
            raise FileExistsError(f"backup manifest already exists: {manifest_path}")
        if _is_link_or_reparse(work_root):
            raise ValueError(f"link or reparse point is not allowed: {work_root}")
        if work_root.exists():
            shutil.rmtree(work_root)
        staging_root = work_root / "staging"
        rollback_root = work_root / "rollback"
        staging_root.mkdir(parents=True)
        rollback_root.mkdir()

        for source in sources:
            shutil.copytree(source, staging_root / source.name, ignore=COPY_IGNORE)

        manifest_skills = []
        for source in sources:
            target = destination_root / source.name
            if target.exists():
                backup_target = backup_root / "productivity" / source.name
                if backup_target.exists() or _is_link_or_reparse(backup_target):
                    raise FileExistsError(f"backup target already exists: {backup_target}")
                backup_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(target, backup_target, ignore=COPY_IGNORE)
                files = _tree_hashes(backup_target)
                existed = True
            else:
                files = {}
                existed = False
            manifest_skills.append(
                {"name": source.name, "existed": existed, "files": files}
            )

        backup_root.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "skills": manifest_skills,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        originals: dict[str, Path] = {}
        try:
            for source in sources:
                name = source.name
                target = destination_root / name
                if target.exists():
                    rollback_target = rollback_root / name
                    target.replace(rollback_target)
                    originals[name] = rollback_target
                activate(staging_root / name, target)
        except BaseException:
            for source in reversed(sources):
                name = source.name
                target = destination_root / name
                if target.exists():
                    shutil.rmtree(target)
                original = originals.get(name)
                if original is not None and original.exists():
                    original.replace(target)
            raise
        return [source.name for source in sources]
    finally:
        if work_root.exists():
            shutil.rmtree(work_root)
        lock_path.unlink(missing_ok=True)


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
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-home", type=Path, default=default_hermes_home())
    parser.add_argument("--backup-dir", type=Path, default=project_root / "backups" / timestamp)
    args = parser.parse_args()

    installed = sync_skills(
        source_root=project_root / "skills" / "productivity",
        hermes_home=args.hermes_home,
        backup_root=args.backup_dir,
    )
    print(json.dumps({
        "status": "installed",
        "skills": installed,
        "hermes_home": str(args.hermes_home),
        "backup_dir": str(args.backup_dir),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
