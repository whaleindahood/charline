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
                self.assertIn("native terminal approval", text)
                self.assertIn("once / deny", text)

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

    def test_charline_entrypoint_is_navigation_over_native_hermes_surfaces(self):
        text = self.read_skill("charline")
        for phrase in (
            "natural language",
            "voice",
            "/commands",
            "domain skill",
            "does not implement a router",
            "does not perform external writes",
            "markdown tables",
            "compact comparisons",
            "/tasks",
        ):
            self.assertIn(phrase, text)

    def test_charline_entrypoint_documents_native_telegram_panel(self):
        text = self.read_skill("charline")
        for phrase in (
            "native telegram inline buttons",
            "календарь",
            "почта",
            "файлы",
            "задачи",
            "проекты",
            "новая задача",
            "same card",
            "existing task center",
            "existing project center",
            "does not start a google operation",
        ):
            self.assertIn(phrase, text)

    def test_calendar_defines_quiet_fast_booking_flow(self):
        text = self.read_skill("charline-calendar")
        for phrase in (
            "duration or end is required from the user",
            "one short clarification",
            "do not send interim commentary",
            "one calendar read",
            "nearest available start",
            "one compact confirmation message",
            "one concise verified result",
            "once / deny",
        ):
            self.assertIn(phrase, text)

    def test_orchestration_defines_native_parallel_task_contract(self):
        text = self.read_skill("charline-orchestration")
        for phrase in (
            "independent tasks",
            "tasks: [...]",
            "background=true",
            "delegation.max_concurrent_children",
            "/background",
            "/topic",
            "/agents",
            "/stop",
            "/goal",
            "dependencies stay sequential",
            "maximum two active subagents",
            "partial failure",
            "ordinary direct-message conversation stays the default",
            "process-local",
            "external write",
            "explicit confirmation",
            "one telegram topic per independent project",
            "do not enable topic mode automatically",
            "root direct message",
            "/projects",
            "recent results",
            "needs input",
        ):
            self.assertIn(phrase, text)

    def test_orchestration_defines_natural_language_cancellation_contract(self):
        text = self.read_skill("charline-orchestration")
        for phrase in (
            "delegate_task(action=\"list\")",
            "delegate_task(action=\"cancel\"",
            "process(action=\"list\")",
            "process(action=\"kill\"",
            "ambiguous stop request",
            "use `clarify`",
            "do not guess",
            "exact target",
            "explicitly asks to stop all",
            "one stop button per task",
            "stop all button",
            "gateway async jobs are service internals",
            "current-chat work only",
            "service jobs stay hidden",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
