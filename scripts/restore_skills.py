"""Restore one checksummed Charline skill backup into an active Hermes home."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.sync_skills import (
    COPY_IGNORE,
    _acquire_lock,
    _is_link_or_reparse,
    _reject_links,
    _tree_hashes,
    default_hermes_home,
    is_managed_skill_name,
)


def _load_manifest(backup_root: Path) -> list[dict[str, object]]:
    manifest_path = backup_root / "manifest.json"
    if not manifest_path.is_file() or _is_link_or_reparse(manifest_path):
        raise ValueError("backup manifest is missing or unsafe")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("backup manifest is invalid") from error
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("backup manifest has unsupported schema")
    skills = manifest.get("skills")
    if not isinstance(skills, list) or not skills:
        raise ValueError("backup manifest must contain skills")

    names: set[str] = set()
    for entry in skills:
        if not isinstance(entry, dict):
            raise ValueError("backup manifest skill entry is invalid")
        name = entry.get("name")
        existed = entry.get("existed")
        files = entry.get("files")
        if (
            not isinstance(name, str)
            or not is_managed_skill_name(name)
            or name in names
            or not isinstance(existed, bool)
            or not isinstance(files, dict)
            or not all(isinstance(key, str) and isinstance(value, str) for key, value in files.items())
        ):
            raise ValueError("backup manifest skill entry is invalid")
        names.add(name)
    return skills


def restore_skills(*, hermes_home: Path, backup_root: Path) -> list[str]:
    """Exception-safe restore; checksum validation happens before profile changes."""
    hermes_home = Path(hermes_home)
    backup_root = Path(backup_root)
    skills = _load_manifest(backup_root)

    for entry in skills:
        name = str(entry["name"])
        if entry["existed"]:
            source = backup_root / "productivity" / name
            if not source.is_dir():
                raise ValueError(f"backup is incomplete for {name}")
            _reject_links(source)
            if _tree_hashes(source) != entry["files"]:
                raise ValueError(f"backup checksum mismatch for {name}")
        elif entry["files"]:
            raise ValueError(f"backup manifest is inconsistent for {name}")

    destination_root = hermes_home / "skills" / "productivity"
    destination_root.mkdir(parents=True, exist_ok=True)
    if _is_link_or_reparse(destination_root):
        raise ValueError(f"link or reparse point is not allowed: {destination_root}")
    for entry in skills:
        target = destination_root / str(entry["name"])
        if _is_link_or_reparse(target):
            raise ValueError(f"link or reparse point is not allowed: {target}")

    lock_path = destination_root / ".charline-sync.lock"
    _acquire_lock(lock_path)
    work_root = destination_root / ".charline-restore-work"
    try:
        if _is_link_or_reparse(work_root):
            raise ValueError(f"link or reparse point is not allowed: {work_root}")
        if work_root.exists():
            shutil.rmtree(work_root)
        staging_root = work_root / "staging"
        rollback_root = work_root / "rollback"
        staging_root.mkdir(parents=True)
        rollback_root.mkdir()

        for entry in skills:
            if entry["existed"]:
                name = str(entry["name"])
                shutil.copytree(
                    backup_root / "productivity" / name,
                    staging_root / name,
                    ignore=COPY_IGNORE,
                )

        originals: dict[str, Path] = {}
        try:
            for entry in skills:
                name = str(entry["name"])
                target = destination_root / name
                if target.exists():
                    rollback_target = rollback_root / name
                    target.replace(rollback_target)
                    originals[name] = rollback_target
                if entry["existed"]:
                    (staging_root / name).replace(target)
        except BaseException:
            for entry in reversed(skills):
                name = str(entry["name"])
                target = destination_root / name
                if target.exists():
                    shutil.rmtree(target)
                original = originals.get(name)
                if original is not None and original.exists():
                    original.replace(target)
            raise
        return [str(entry["name"]) for entry in skills]
    finally:
        if work_root.exists():
            shutil.rmtree(work_root)
        lock_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup_dir", type=Path)
    parser.add_argument("--hermes-home", type=Path, default=default_hermes_home())
    args = parser.parse_args()
    restored = restore_skills(hermes_home=args.hermes_home, backup_root=args.backup_dir)
    print(json.dumps({"status": "restored", "skills": restored}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
