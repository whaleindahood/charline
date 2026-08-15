import tempfile
import unittest
from subprocess import CompletedProcess
from pathlib import Path
from unittest.mock import patch

from scripts.health_check import collect_health, default_runner


class HealthCheckTests(unittest.TestCase):
    def make_healthy_fixture(self, base):
        project = base / "project"
        hermes = base / "hermes"
        (project / ".git").mkdir(parents=True)
        source = project / "skills" / "productivity" / "charline"
        target = hermes / "skills" / "productivity" / "charline"
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

    def test_reports_degraded_when_managed_skill_source_tree_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            hermes = base / "hermes"
            (project / ".git").mkdir(parents=True)

            result = collect_health(
                project_root=project,
                hermes_home=hermes,
                runner=lambda command: (0, "ok"),
            )

            self.assertEqual(result["status"], "degraded")
            self.assertFalse(result["checks"]["managed_skills"]["ok"])
            self.assertEqual(result["checks"]["managed_skills"]["detail"]["count"], 0)


    def test_reports_degraded_when_any_file_in_the_installed_skill_tree_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, hermes = self.make_healthy_fixture(Path(tmp))
            source = project / "skills" / "productivity" / "charline"
            target = hermes / "skills" / "productivity" / "charline"
            (source / "references").mkdir()
            (target / "references").mkdir()
            (source / "references" / "policy.md").write_text("repo policy", encoding="utf-8")
            (target / "references" / "policy.md").write_text("stale policy", encoding="utf-8")
            result = collect_health(project_root=project, hermes_home=hermes, runner=lambda command: (0, "ok"))
            self.assertEqual(result["status"], "degraded")
            self.assertFalse(result["checks"]["managed_skills"]["ok"])
            self.assertEqual(result["checks"]["managed_skills"]["detail"]["mismatched"], ["charline"])

    def test_reports_degraded_when_active_profile_has_extra_charline_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, hermes = self.make_healthy_fixture(Path(tmp))
            stale = hermes / "skills" / "productivity" / "charline-stale"
            stale.mkdir()
            (stale / "SKILL.md").write_text("stale", encoding="utf-8")
            result = collect_health(
                project_root=project,
                hermes_home=hermes,
                runner=lambda command: (0, "ok"),
            )
            self.assertEqual(result["status"], "degraded")
            self.assertEqual(
                result["checks"]["managed_skills"]["detail"]["extra"],
                ["charline-stale"],
            )

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

    @patch("scripts.health_check.subprocess.run")
    def test_default_runner_retries_windows_access_violation_once(self, run):
        run.side_effect = [
            CompletedProcess(["hermes"], 3221225477, "", ""),
            CompletedProcess(["hermes"], 0, "ok", ""),
        ]

        self.assertEqual(default_runner(["hermes", "config", "check"]), (0, "ok"))
        self.assertEqual(run.call_count, 2)

    @patch("scripts.health_check.subprocess.run")
    def test_default_runner_retries_windows_permission_error_and_second_crash(self, run):
        run.side_effect = [
            PermissionError(13, "permission denied"),
            CompletedProcess(["hermes"], 3221225477, "", ""),
            CompletedProcess(["hermes"], 0, "valid", ""),
        ]

        self.assertEqual(default_runner(["hermes", "config", "check"]), (0, "valid"))
        self.assertEqual(run.call_count, 3)

    @patch("scripts.health_check.subprocess.run")
    def test_default_runner_retries_uv_trampoline_permission_text(self, run):
        run.side_effect = [
            CompletedProcess(
                ["hermes"],
                1,
                "",
                "error: uv trampoline failed to spawn Python child process\n"
                "Caused by: permission denied (os error 5)",
            ),
            CompletedProcess(["hermes"], 0, "valid", ""),
        ]

        self.assertEqual(default_runner(["hermes", "config", "check"]), (0, "valid"))
        self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
