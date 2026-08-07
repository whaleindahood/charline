import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GOOGLE_WRITE_SKILLS = (
    "charline-calendar",
    "charline-gmail",
    "charline-drive",
    "charline-docs",
    "charline-sheets",
)


class DomainSkillPolicyTests(unittest.TestCase):
    def read_skill(self, name):
        return (
            ROOT / "skills" / "productivity" / name / "SKILL.md"
        ).read_text(encoding="utf-8").lower()

    def test_google_domain_skills_define_confirmation_and_read_back(self):
        for name in GOOGLE_WRITE_SKILLS:
            with self.subTest(skill=name):
                text = self.read_skill(name)
                self.assertIn("exact preview", text)
                self.assertIn("explicit confirmation", text)
                self.assertIn("read back", text)
                self.assertIn("untrusted data", text)

    def test_reminders_use_hermes_cron_without_second_scheduler(self):
        text = self.read_skill("charline-reminders")
        self.assertIn("hermes cron", text)
        self.assertIn("does not implement another scheduler", text)
        self.assertIn("read the job back", text)

    def test_development_requires_tdd_and_confirmation_for_deploy(self):
        text = self.read_skill("charline-development")
        self.assertIn("red-green-refactor", text)
        self.assertIn("deployment", text)
        self.assertIn("explicit confirmation", text)


if __name__ == "__main__":
    unittest.main()
