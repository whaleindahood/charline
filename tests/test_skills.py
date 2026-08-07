import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = {
    "charline-orchestration",
    "charline-workspace",
    "charline-calendar",
    "charline-research",
    "charline-briefing",
    "charline-command-center",
    "charline-development",
    "charline-docs",
    "charline-drive",
    "charline-gmail",
    "charline-reminders",
    "charline-sheets",
}


class SkillContractTests(unittest.TestCase):
    def test_managed_skills_have_valid_frontmatter_and_required_sections(self):
        for name in sorted(SKILLS):
            with self.subTest(skill=name):
                path = ROOT / "skills" / "productivity" / name / "SKILL.md"
                content = path.read_text(encoding="utf-8")
                self.assertTrue(content.startswith("---\n"))
                match = re.match(r"---\n(.*?)\n---\n(.*)", content, re.DOTALL)
                self.assertIsNotNone(match)
                frontmatter, body = match.groups()
                self.assertRegex(frontmatter, rf"(?m)^name:\s*{re.escape(name)}\s*$")
                description = re.search(r"(?m)^description:\s*(.+)$", frontmatter)
                self.assertIsNotNone(description)
                self.assertLessEqual(len(description.group(1).strip().strip('"')), 1024)
                for heading in ("# ", "## Overview", "## When to Use", "## Verification Checklist"):
                    self.assertIn(heading, body)


if __name__ == "__main__":
    unittest.main()
