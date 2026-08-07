import tempfile
import unittest
from subprocess import CompletedProcess
from pathlib import Path
from unittest.mock import patch

from scripts.runtime_check import collect_runtime, default_hermes_home, default_runner


class RuntimeCheckTests(unittest.TestCase):
    def test_accepts_supported_hermes_020_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            hermes_home = Path(tmp)

            def runner(command):
                joined = " ".join(map(str, command))
                if "--version" in joined:
                    return 0, "Hermes Agent v0.20.0 (test)"
                if "config check" in joined:
                    return 0, "✓ TELEGRAM_BOT_TOKEN\n✓ TELEGRAM_ALLOWED_USERS"
                if "gateway status" in joined:
                    return 0, "Gateway process running (PID: 123)"
                return 0, "doctor ok"

            result = collect_runtime(hermes_home, runner)
            self.assertTrue(result["checks"]["hermes_version"]["ok"])

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
                    return 0, "✓ TELEGRAM_BOT_TOKEN\n✓ TELEGRAM_ALLOWED_USERS"
                if "gateway status" in joined:
                    return 0, "Gateway process running (PID: 123)"
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
                return 0, "✓ TELEGRAM_BOT_TOKEN\n✓ TELEGRAM_ALLOWED_USERS"

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
                    return 0, "✓ TELEGRAM_BOT_TOKEN\n✓ TELEGRAM_ALLOWED_USERS"
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

    def test_unset_telegram_fields_do_not_pass_config_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            def runner(command):
                joined = " ".join(map(str, command))
                if "--version" in joined:
                    return 0, "Hermes Agent v0.19.0"
                if "config check" in joined:
                    return 0, "○ TELEGRAM_BOT_TOKEN\n○ TELEGRAM_ALLOWED_USERS"
                if "gateway status" in joined:
                    return 0, "Running\nPID(s): 123"
                return 0, "doctor ok"

            result = collect_runtime(Path(tmp), runner, check_live_google=False)
            self.assertFalse(result["checks"]["config"]["ok"])

    @patch("scripts.runtime_check.subprocess.run")
    def test_default_runner_retries_windows_access_violation_once(self, run):
        run.side_effect = [
            CompletedProcess(["hermes"], 3221225477, "", ""),
            CompletedProcess(["hermes"], 0, "ok", ""),
        ]

        self.assertEqual(default_runner(["hermes", "doctor"]), (0, "ok"))
        self.assertEqual(run.call_count, 2)
        self.assertTrue(all(call.kwargs["timeout"] == 90 for call in run.call_args_list))

    @patch("scripts.runtime_check.subprocess.run")
    def test_default_runner_retries_windows_permission_error_and_second_crash(self, run):
        run.side_effect = [
            PermissionError(13, "permission denied"),
            CompletedProcess(["hermes"], 3221225477, "", ""),
            CompletedProcess(["hermes"], 0, "ready", ""),
        ]

        self.assertEqual(default_runner(["hermes", "--version"]), (0, "ready"))
        self.assertEqual(run.call_count, 3)

    @patch("scripts.runtime_check.subprocess.run")
    def test_default_runner_retries_uv_trampoline_permission_text(self, run):
        run.side_effect = [
            CompletedProcess(
                ["hermes"],
                1,
                "",
                "error: uv trampoline failed to spawn Python child process\n"
                "Caused by: permission denied (os error 5)",
            ),
            CompletedProcess(["hermes"], 0, "ready", ""),
        ]

        self.assertEqual(default_runner(["hermes", "doctor"]), (0, "ready"))
        self.assertEqual(run.call_count, 2)

    def test_live_google_uses_base_python_when_venv_launcher_is_unreliable(self):
        with tempfile.TemporaryDirectory() as tmp:
            hermes_home = Path(tmp)
            setup = (
                hermes_home
                / "skills"
                / "productivity"
                / "google-workspace"
                / "scripts"
                / "setup.py"
            )
            setup.parent.mkdir(parents=True)
            setup.write_text("", encoding="utf-8")
            venv = hermes_home / "hermes-agent" / "venv"
            base = hermes_home / "stable-python"
            (venv / "Lib" / "site-packages").mkdir(parents=True)
            base.mkdir()
            (base / "python.exe").write_text("", encoding="utf-8")
            (venv / "pyvenv.cfg").write_text(
                f"home = {base}\nversion_info = 3.11.9\n",
                encoding="utf-8",
            )
            commands = []

            def runner(command):
                commands.append(list(map(str, command)))
                joined = " ".join(map(str, command))
                if "--version" in joined:
                    return 0, "Hermes Agent v0.19.0"
                if "config check" in joined:
                    return 0, "✓ TELEGRAM_BOT_TOKEN\n✓ TELEGRAM_ALLOWED_USERS"
                if "gateway status" in joined:
                    return 0, "Gateway process running (PID: 123)"
                return 0, "ok"

            collect_runtime(hermes_home, runner, check_live_google=True)
            google_command = next(command for command in commands if "--check-live" in " ".join(command))
            self.assertEqual(google_command[0], str(base / "python.exe"))
            self.assertIn("site-packages", " ".join(google_command))


if __name__ == "__main__":
    unittest.main()
