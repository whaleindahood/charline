"""Executable deterministic runner for Charline policy traces.

This validates observed/synthetic action traces. It does not call Hermes,
a model, or an external API and is not an end-to-end behavioral evaluation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from evals.policy_contract import evaluate_trace, validate_scenarios


def evaluate_suite(scenarios: object, traces: object) -> dict[str, object]:
    schema_errors = validate_scenarios(scenarios)
    trace_map = traces if isinstance(traces, Mapping) else {}
    results: list[dict[str, object]] = []

    if isinstance(scenarios, list):
        for scenario in scenarios:
            if not isinstance(scenario, Mapping):
                continue
            scenario_id = scenario.get("id")
            if not isinstance(scenario_id, str) or not scenario_id:
                continue
            raw_trace = trace_map.get(scenario_id)
            if raw_trace is None:
                violations = ["missing trace"]
            elif not isinstance(raw_trace, Sequence) or isinstance(raw_trace, (str, bytes)):
                violations = ["trace must be a sequence of action strings"]
            elif not all(isinstance(action, str) and action for action in raw_trace):
                violations = ["trace must contain non-empty action strings"]
            else:
                violations = evaluate_trace(scenario, raw_trace)
            results.append({"id": scenario_id, "violations": violations})

    passed = sum(not result["violations"] for result in results)
    failed = len(results) - passed
    status = "passed" if not schema_errors and failed == 0 else "failed"
    return {
        "status": status,
        "schema_errors": schema_errors,
        "passed": passed,
        "failed": failed,
        "results": results,
    }
