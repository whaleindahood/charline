from pathlib import Path


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
