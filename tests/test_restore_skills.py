import json
import tempfile
import unittest
from pathlib import Path

from scripts.restore_skills import restore_skills
from scripts.sync_skills import sync_skills


class RestoreSkillsTests(unittest.TestCase):
    def make_skill(self, root, name, content):
        skill = root / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(content, encoding="utf-8")
        return skill

    def test_restores_old_skill_and_removes_skill_absent_before_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "source"
            hermes = base / "hermes"
            backup = base / "backup"
            self.make_skill(source, "charline", "new entrypoint")
            self.make_skill(source, "charline-old", "new old")
            self.make_skill(source, "charline-added", "new added")
            active = hermes / "skills" / "productivity"
            self.make_skill(active, "charline", "original entrypoint")
            self.make_skill(active, "charline-old", "original old")

            sync_skills(source_root=source, hermes_home=hermes, backup_root=backup)
            (active / "charline-old" / "SKILL.md").write_text("later mutation", encoding="utf-8")

            restored = restore_skills(hermes_home=hermes, backup_root=backup)

            self.assertEqual(sorted(restored), ["charline", "charline-added", "charline-old"])
            self.assertEqual(
                (active / "charline" / "SKILL.md").read_text(encoding="utf-8"),
                "original entrypoint",
            )
            self.assertEqual(
                (active / "charline-old" / "SKILL.md").read_text(encoding="utf-8"),
                "original old",
            )
            self.assertFalse((active / "charline-added").exists())

    def test_rejects_checksum_mismatch_before_changing_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "source"
            hermes = base / "hermes"
            backup = base / "backup"
            self.make_skill(source, "charline-a", "new")
            active = hermes / "skills" / "productivity"
            self.make_skill(active, "charline-a", "original")
            sync_skills(source_root=source, hermes_home=hermes, backup_root=backup)
            (backup / "productivity" / "charline-a" / "SKILL.md").write_text(
                "tampered", encoding="utf-8"
            )

            with self.assertRaisesRegex(ValueError, "checksum"):
                restore_skills(hermes_home=hermes, backup_root=backup)

            self.assertEqual(
                (active / "charline-a" / "SKILL.md").read_text(encoding="utf-8"),
                "new",
            )

    def test_rejects_incomplete_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            backup = base / "backup"
            backup.mkdir()
            (backup / "manifest.json").write_text(
                json.dumps({"schema_version": 1}), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "manifest"):
                restore_skills(hermes_home=base / "hermes", backup_root=backup)

    def test_rejects_manifest_skill_name_with_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            backup = base / "backup"
            backup.mkdir()
            (backup / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "skills": [
                            {
                                "name": "charline-../../outside",
                                "existed": False,
                                "files": {},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "manifest"):
                restore_skills(hermes_home=base / "hermes", backup_root=backup)

            self.assertFalse((base / "hermes").exists())


if __name__ == "__main__":
    unittest.main()
