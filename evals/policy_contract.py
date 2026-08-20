"""Deterministic policy checks for V1 specification fixtures.

This module evaluates symbolic action traces only. It does not invoke a model,
Hermes, or an external API and must not be presented as an end-to-end eval.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence


WRITE_SEQUENCE = (
    "exact_preview",
    "explicit_confirmation",
    "external_write",
    "read_back",
)
ALLOWED_WRITE_POLICIES = {"none", "confirm", "confirmed-test-only"}
EXECUTION_STRATEGIES = {
    "direct",
    "delegation",
    "background",
    "kanban",
    "cron",
    "project_topic",
    "calendar_fast_path",
    "normal_calendar",
}


def validate_scenarios(scenarios: object) -> list[str]:
    """Return deterministic schema/policy errors for scenario fixtures."""
    if not isinstance(scenarios, list):
        return ["scenario document must be a list"]

    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, scenario in enumerate(scenarios):
        prefix = f"scenario[{index}]"
        if not isinstance(scenario, dict):
            errors.append(f"{prefix} must be an object")
            continue

        scenario_id = scenario.get("id")
        if not isinstance(scenario_id, str) or not scenario_id:
            errors.append(f"{prefix} must have a non-empty id")
        elif scenario_id in seen_ids:
            errors.append(f"{prefix} has duplicate id {scenario_id!r}")
        else:
            seen_ids.add(scenario_id)

        if not isinstance(scenario.get("request"), str) or not scenario["request"]:
            errors.append(f"{prefix} must have a non-empty request")
        expected = scenario.get("expected")
        if not isinstance(expected, list) or not expected or not all(
            isinstance(item, str) and item for item in expected
        ):
            errors.append(f"{prefix} must have non-empty expected strings")
        if scenario.get("external_write") not in ALLOWED_WRITE_POLICIES:
            errors.append(f"{prefix} has an invalid external_write policy")
        strategy = scenario.get("execution_strategy")
        if strategy is not None and strategy not in EXECUTION_STRATEGIES:
            errors.append(f"{prefix} has an invalid execution_strategy")

        required_trace = scenario.get("required_trace", [])
        if not isinstance(required_trace, list) or not all(
            isinstance(item, str) and item for item in required_trace
        ):
            errors.append(f"{prefix} required_trace must contain strings")

    if len(scenarios) < 8:
        errors.append("V1 contract requires at least eight scenarios")
    return errors


def evaluate_trace(scenario: Mapping[str, object], trace: Iterable[str]) -> list[str]:
    """Evaluate a symbolic trace against one fixture's bounded policy contract."""
    actions = list(trace)
    violations: list[str] = []
    write_policy = scenario.get("external_write")
    strategy = scenario.get("execution_strategy")

    if isinstance(strategy, str):
        observed = [action for action in actions if action.startswith("strategy:")]
        expected = f"strategy:{strategy}"
        if observed != [expected]:
            violations.append(
                f"expected execution strategy {strategy!r}, observed {observed or 'none'}"
            )

    if write_policy == "none" and "external_write" in actions:
        violations.append("read-only scenario performed an external write")

    if write_policy in {"confirm", "confirmed-test-only"}:
        if actions.count("external_write") != 1:
            violations.append("external write must execute exactly once")
        positions = {action: _first_index(actions, action) for action in WRITE_SEQUENCE}
        if positions["external_write"] is not None:
            if (
                positions["explicit_confirmation"] is None
                or positions["explicit_confirmation"] > positions["external_write"]
            ):
                violations.append("write must follow explicit confirmation")
            else:
                write_index = positions["external_write"]
                preview_indexes = [
                    index
                    for index, action in enumerate(actions[:write_index])
                    if action == "exact_preview"
                ]
                confirmation_indexes = [
                    index
                    for index, action in enumerate(actions[:write_index])
                    if action == "explicit_confirmation"
                ]
                if (
                    preview_indexes
                    and confirmation_indexes
                    and confirmation_indexes[-1] < preview_indexes[-1]
                ):
                    violations.append("latest preview must be explicitly confirmed")
        if any(position is None for position in positions.values()):
            violations.append("write trace must include preview, confirmation, write, and read-back")
        elif [positions[action] for action in WRITE_SEQUENCE] != sorted(
            positions[action] for action in WRITE_SEQUENCE
        ):
            violations.append("write trace phases are out of order")

    required = scenario.get("required_trace", [])
    if isinstance(required, Sequence) and not isinstance(required, (str, bytes)):
        missing = [action for action in required if action not in actions]
        if missing:
            violations.append("missing required trace actions: " + ", ".join(missing))
    return violations


def _first_index(actions: list[str], action: str) -> int | None:
    try:
        return actions.index(action)
    except ValueError:
        return None
