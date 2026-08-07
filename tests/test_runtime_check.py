import tempfile
import unittest
from subprocess import CompletedProcess
from pathlib import Path
from unittest.mock import patch

from scripts.runtime_check import collect_runtime, default_hermes_home, default_runner


class RuntimeCheckTests(unittest.TestCase):
    def test_reports_ready_for_supported_single_gateway_and_live_google(self):
        with tempfile.TemporaryDirectory() as tmp:
            hermes_home = Path(tmp)
            google_script = (
                hermes_home
                / "skills"
                / "productivity"
                / "google-workspace"
                / "scripts"
                / "setup.py"
            )
            google_script.parent.mkdir(parents=True)
            google_script.write_text("", encoding="utf-8")

            def runner(command):
                joined = " ".join(map(str, command))
                if "--version" in joined:
                    return 0, "Hermes Agent v0.19.0 (test)"
                if "config check" in joined:
                    return 0, "TELEGRAM_BOT_TOKEN TELEGRAM_ALLOWED_USERS"
                if "gateway status" in joined:
                    return 0, "Running\nPID(s): 123"
                if "--check-live" in joined:
                    return 0, "AUTHENTICATED LIVE_OK"
                return 0, "doctor ok"

            result = collect_runtime(
                hermes_home=hermes_home,
                runner=runner,
                check_live_google=True,
            )
            self.assertEqual(result["status"], "ready")
            self.assertTrue(result["live_runtime_verified"])
            self.assertTrue(all(check["ok"] for check in result["checks"].values()))

    def test_reports_degraded_when_doctor_or_gateway_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            hermes_home = Path(tmp)

            def runner(command):
                joined = " ".join(map(str, command))
                if "--version" in joined:
                    return 0, "Hermes Agent v0.19.0"
                if "doctor" in joined:
                    return 1, "SQLite vulnerable"
                if "gateway status" in joined:
                    return 1, "Gateway stopped"
                return 0, "TELEGRAM_BOT_TOKEN TELEGRAM_ALLOWED_USERS"

            result = collect_runtime(
                hermes_home=hermes_home,
                runner=runner,
                check_live_google=False,
            )
            self.assertEqual(result["status"], "degraded")
            self.assertFalse(result["checks"]["doctor"]["ok"])
            self.assertFalse(result["checks"]["single_gateway"]["ok"])
            self.assertFalse(result["live_runtime_verified"])

    def test_runner_exception_becomes_diagnostic_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = collect_runtime(
                hermes_home=Path(tmp),
                runner=lambda command: (_ for _ in ()).throw(OSError("launch failed")),
                check_live_google=False,
            )
            self.assertEqual(result["status"], "degraded")
            self.assertIn("launch failed", result["checks"]["hermes_version"]["detail"])

    def test_default_home_uses_windows_local_app_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(
                "os.environ",
                {"LOCALAPPDATA": tmp},
                clear=True,
            ):
                self.assertEqual(default_hermes_home(), Path(tmp) / "hermes")

    def test_doctor_security_finding_blocks_readiness_even_with_zero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            def runner(command):
                joined = " ".join(map(str, command))
                if "--version" in joined:
                    return 0, "Hermes Agent v0.19.0"
                if "config check" in joined:
                    return 0, "TELEGRAM_BOT_TOKEN TELEGRAM_ALLOWED_USERS"
                if "gateway status" in joined:
                    return 0, "Running\nPID(s): 123"
                if "doctor" in joined:
                    return 0, "SQLite 3.45.1 is vulnerable to the WAL-reset bug"
                return 0, "ok"

            result = collect_runtime(Path(tmp), runner, check_live_google=False)
            self.assertFalse(result["checks"]["doctor"]["ok"])
            self.assertEqual(
                result["checks"]["doctor"]["blocking_findings"],
                ["sqlite-wal-reset"],
            )

    @patch("scripts.runtime_check.subprocess.run")
    def test_default_runner_retries_windows_access_violation_once(self, run):
        run.side_effect = [
            CompletedProcess(["hermes"], 3221225477, "", ""),
            CompletedProcess(["hermes"], 0, "ok", ""),
        ]

        self.assertEqual(default_runner(["hermes", "doctor"]), (0, "ok"))
        self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
