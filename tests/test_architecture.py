from pathlib import Path
import tomllib


ROOT = Path(__file__).parents[1]


def test_deterministic_core_does_not_import_runtime_or_service_sdks():
    forbidden = ("telegram", "googleapiclient", "fastapi", "apscheduler")
    violations = []
    for path in sorted((ROOT / "src" / "charline").glob("*.py")):
        text = path.read_text(encoding="utf-8").lower()
        for module in forbidden:
            if f"import {module}" in text or f"from {module}" in text:
                violations.append(f"{path.name}: {module}")
    assert violations == []


def test_v1_contains_no_second_runtime_or_mini_app_tree():
    forbidden_dirs = {"miniapp", "mini-app", "gateway", "scheduler", "router"}
    present = {
        path.name.lower()
        for path in ROOT.iterdir()
        if path.is_dir() and path.name.lower() in forbidden_dirs
    }
    assert present == set()


def test_charline_plugin_does_not_implement_session_or_routing_state():
    plugin_root = ROOT / "plugins" / "charline"
    combined = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in plugin_root.glob("*.py")
    )
    for forbidden in (
        "sqlite3",
        "session database",
        "last_project",
        "active_project",
        "create_task(",
        "apscheduler",
        "telegram.bot(",
    ):
        assert forbidden not in combined
    assert 'register_command(\n        name="topic"' not in combined


def test_fresh_development_sync_installs_pytest():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev_dependencies = config.get("dependency-groups", {}).get("dev", [])
    assert any(dependency.startswith("pytest") for dependency in dev_dependencies)


def test_gateway_launcher_retries_only_immediate_startup_failures():
    text = (ROOT / "scripts" / "Hermes_Gateway.vbs").read_text(encoding="utf-8")
    assert "pyvenv.cfg" in text
    assert 'base_home & "\\python.exe"' in text
    assert "\\.venv\\Lib\\site-packages" in text
    assert "attempt >= 3" in text
    assert "elapsed >= 30" in text
    assert "WScript.Sleep" in text


def test_hermes_patch_is_pinned_and_carries_runtime_tests():
    patch_root = ROOT / "patches" / "hermes-agent"
    base = (patch_root / "BASE_COMMIT").read_text(encoding="utf-8").strip()
    patch = (patch_root / "charline.patch").read_text(encoding="utf-8")
    assert len(base) == 40
    assert "hermes_cli/platform_actions.py" in patch
    assert "ensure_private_topic" in patch
    assert "tests/hermes_cli/test_platform_actions.py" in patch
    assert "send_card" in patch
    assert "plugin_callback" in patch
    assert "command_menu" in patch
    assert "interrupt_delegation" in patch
    assert "gateway/slash_commands.py" not in patch


def test_phase_two_ui_keeps_old_stateful_core_menus_deleted():
    patch = (ROOT / "patches" / "hermes-agent" / "charline.patch").read_text(encoding="utf-8")
    plugin = (ROOT / "plugins" / "charline" / "__init__.py").read_text(encoding="utf-8")
    for obsolete in (
        "send_charline_menu", "_charline_menu_state", "_automation_menu_state",
        "project_summary_event", "last_project", "active_project",
    ):
        assert obsolete not in patch
        assert obsolete not in plugin
