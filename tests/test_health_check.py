import tempfile
import unittest
from pathlib import Path

from scripts.health_check import collect_health


class HealthCheckTests(unittest.TestCase):
    def make_healthy_fixture(self, base):
        project = base / "project"
        hermes = base / "hermes"
        (project / ".git").mkdir(parents=True)
        source = project / "skills" / "productivity" / "charline-test"
        target = hermes / "skills" / "productivity" / "charline-test"
        source.mkdir(parents=True)
        target.mkdir(parents=True)
        (source / "SKILL.md").write_text("managed", encoding="utf-8")
        (target / "SKILL.md").write_text("managed", encoding="utf-8")
        (hermes / "google_token.json").write_text("not-read", encoding="utf-8")
        (hermes / "google_client_secret.json").write_text("not-read", encoding="utf-8")
        return project, hermes

    def test_reports_consistent_for_independent_repo_synced_skills_and_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, hermes = self.make_healthy_fixture(Path(tmp))
            def runner(command):
                return 0, "Hermes Agent test" if "--version" in command else "Config version: 33"
            result = collect_health(project_root=project, hermes_home=hermes, runner=runner)
            self.assertEqual(result["status"], "consistent")
            self.assertEqual(result["scope"], "repo-profile-consistency")
            self.assertFalse(result["live_runtime_verified"])
            self.assertTrue(all(check["ok"] for check in result["checks"].values()))

    def test_reports_degraded_when_hermes_command_cannot_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, hermes = self.make_healthy_fixture(Path(tmp))
            def failing_runner(command):
                raise FileNotFoundError("hermes missing")
            result = collect_health(project_root=project, hermes_home=hermes, runner=failing_runner)
            self.assertEqual(result["status"], "degraded")
            self.assertFalse(result["checks"]["hermes_version"]["ok"])
            self.assertIn("hermes missing", result["checks"]["hermes_version"]["detail"])


    def test_reports_degraded_when_any_file_in_the_installed_skill_tree_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, hermes = self.make_healthy_fixture(Path(tmp))
            source = project / "skills" / "productivity" / "charline-test"
            target = hermes / "skills" / "productivity" / "charline-test"
            (source / "references").mkdir()
            (target / "references").mkdir()
            (source / "references" / "policy.md").write_text("repo policy", encoding="utf-8")
            (target / "references" / "policy.md").write_text("stale policy", encoding="utf-8")
            result = collect_health(project_root=project, hermes_home=hermes, runner=lambda command: (0, "ok"))
            self.assertEqual(result["status"], "degraded")
            self.assertFalse(result["checks"]["managed_skills"]["ok"])
            self.assertEqual(result["checks"]["managed_skills"]["detail"]["mismatched"], ["charline-test"])

    def test_reports_degraded_instead_of_raising_on_unexpected_runner_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, hermes = self.make_healthy_fixture(Path(tmp))
            def failing_runner(command):
                raise RuntimeError("runner exploded")
            result = collect_health(project_root=project, hermes_home=hermes, runner=failing_runner)
            self.assertEqual(result["status"], "degraded")
            self.assertFalse(result["checks"]["hermes_version"]["ok"])
            self.assertFalse(result["checks"]["hermes_config"]["ok"])
            self.assertIn("runner exploded", result["checks"]["hermes_config"]["detail"])


if __name__ == "__main__":
    unittest.main()
