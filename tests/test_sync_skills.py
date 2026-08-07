import os
import tempfile
import unittest
from pathlib import Path

from scripts.sync_skills import sync_skills


ROOT = Path(__file__).resolve().parents[1]


class SyncSkillsTests(unittest.TestCase):
    def make_skill(self, root, name, content):
        skill = root / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(content, encoding="utf-8")
        return skill

    def test_installs_all_managed_skills_and_backs_up_existing_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            hermes_home = base / "hermes"
            existing = hermes_home / "skills" / "productivity" / "charline-orchestration"
            existing.mkdir(parents=True)
            (existing / "SKILL.md").write_text("old skill", encoding="utf-8")
            backup = base / "backup"
            installed = sync_skills(source_root=ROOT / "skills" / "productivity", hermes_home=hermes_home, backup_root=backup)
            self.assertEqual(len(installed), 5)
            self.assertIn("charline-orchestration", installed)
            self.assertTrue((backup / "productivity" / "charline-orchestration" / "SKILL.md").exists())
            for name in installed:
                target = hermes_home / "skills" / "productivity" / name / "SKILL.md"
                self.assertTrue(target.exists())
                self.assertIn(f"name: {name}", target.read_text(encoding="utf-8"))

    def test_does_not_install_runtime_temp_or_python_cache_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source_root = base / "source"
            skill = self.make_skill(source_root, "charline-a", "name: charline-a\n")
            (skill / ".hermes-tmp.partial").write_text("temp", encoding="utf-8")
            cache = skill / "__pycache__"
            cache.mkdir()
            (cache / "module.pyc").write_bytes(b"cache")

            sync_skills(
                source_root=source_root,
                hermes_home=base / "hermes",
                backup_root=base / "backup",
            )

            target = base / "hermes" / "skills" / "productivity" / "charline-a"
            self.assertFalse((target / ".hermes-tmp.partial").exists())
            self.assertFalse((target / "__pycache__").exists())

    def test_rolls_back_all_skills_when_activation_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source_root = base / "source"
            hermes_home = base / "hermes"
            destination_root = hermes_home / "skills" / "productivity"
            for name in ("charline-a", "charline-b"):
                source = source_root / name
                target = destination_root / name
                source.mkdir(parents=True)
                target.mkdir(parents=True)
                (source / "SKILL.md").write_text(f"name: {name}\nnew", encoding="utf-8")
                (target / "SKILL.md").write_text(f"name: {name}\nold", encoding="utf-8")
            calls = 0
            def fail_second_activation(staging, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected activation failure")
                staging.replace(target)
            with self.assertRaisesRegex(OSError, "injected activation failure"):
                sync_skills(source_root=source_root, hermes_home=hermes_home, backup_root=base / "backup", activate=fail_second_activation)
            for name in ("charline-a", "charline-b"):
                self.assertEqual((destination_root / name / "SKILL.md").read_text(encoding="utf-8"), f"name: {name}\nold")
            self.assertFalse((destination_root / ".charline-sync.lock").exists())
            self.assertEqual([p.name for p in destination_root.iterdir() if p.name.startswith(".charline-sync-")], [])

    def test_rejects_an_active_sync_lock_without_changing_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source_root = base / "source"
            destination_root = base / "hermes" / "skills" / "productivity"
            self.make_skill(source_root, "charline-a", "name: charline-a\nnew")
            target = self.make_skill(destination_root, "charline-a", "name: charline-a\nold")
            (destination_root / ".charline-sync.lock").write_text("busy", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "already in progress"):
                sync_skills(source_root=source_root, hermes_home=base / "hermes", backup_root=base / "backup")
            self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "name: charline-a\nold")

    def test_rejects_backup_that_overlaps_the_source_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source_root = base / "source"
            self.make_skill(source_root, "charline-a", "name: charline-a\nnew")
            with self.assertRaisesRegex(ValueError, "overlap"):
                sync_skills(source_root=source_root, hermes_home=base / "hermes", backup_root=source_root / "backup")
            self.assertFalse((base / "hermes").exists())

    def test_rejects_links_anywhere_in_a_managed_source_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source_root = base / "source"
            skill = self.make_skill(source_root, "charline-a", "name: charline-a\nnew")
            outside = base / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            try:
                os.symlink(outside, skill / "linked.txt")
            except OSError as error:
                self.skipTest(f"symlink creation unavailable: {error}")
            with self.assertRaisesRegex(ValueError, "link or reparse point"):
                sync_skills(source_root=source_root, hermes_home=base / "hermes", backup_root=base / "backup")
            self.assertFalse((base / "hermes").exists())

    def test_rejects_a_linked_existing_target_without_touching_its_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source_root = base / "source"
            self.make_skill(source_root, "charline-a", "name: charline-a\nnew")
            destination_root = base / "hermes" / "skills" / "productivity"
            destination_root.mkdir(parents=True)
            outside = self.make_skill(base / "outside", "real", "name: charline-a\noutside")
            target = destination_root / "charline-a"
            try:
                os.symlink(outside, target, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"directory symlink creation unavailable: {error}")
            with self.assertRaisesRegex(ValueError, "link or reparse point"):
                sync_skills(source_root=source_root, hermes_home=base / "hermes", backup_root=base / "backup")
            self.assertEqual((outside / "SKILL.md").read_text(encoding="utf-8"), "name: charline-a\noutside")


if __name__ == "__main__":
    unittest.main()
