"""Deterministic usage-budget evaluation over Hermes-owned counters."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass


COUNTERS = (
    "message_count",
    "api_call_count",
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
)


@dataclass(frozen=True)
class UsageBudget:
    max_messages_per_session: int = 120
    max_api_calls_per_session: int = 300
    max_input_tokens_per_session: int = 250_000
    max_cache_read_tokens_per_session: int = 5_000_000
    max_active_subagents: int = 2


def _counter(row: Mapping[str, object], name: str) -> int:
    value = row.get(name, 0)
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def summarize_usage(
    rows: Iterable[Mapping[str, object]],
    *,
    active_subagents: int,
    budget: UsageBudget,
) -> dict[str, object]:
    if isinstance(active_subagents, bool) or active_subagents < 0:
        raise ValueError("active_subagents must be a non-negative integer")
    totals = {name: 0 for name in COUNTERS}
    by_source: defaultdict[str, dict[str, int]] = defaultdict(
        lambda: {name: 0 for name in COUNTERS}
    )
    alerts: list[str] = []
    session_count = 0

    for row in rows:
        session_count += 1
        session_id = str(row.get("id") or "unknown")
        source = str(row.get("source") or "unknown")
        values = {name: _counter(row, name) for name in COUNTERS}
        for name, value in values.items():
            totals[name] += value
            by_source[source][name] += value
        if values["message_count"] >= budget.max_messages_per_session:
            alerts.append(f"rotate_session:{session_id}:messages")
        if values["api_call_count"] >= budget.max_api_calls_per_session:
            alerts.append(f"review_session:{session_id}:api_calls")
        if values["input_tokens"] >= budget.max_input_tokens_per_session:
            alerts.append(f"rotate_session:{session_id}:input_tokens")
        if values["cache_read_tokens"] >= budget.max_cache_read_tokens_per_session:
            alerts.append(f"rotate_session:{session_id}:cache_read_tokens")

    if active_subagents > budget.max_active_subagents:
        alerts.append(
            f"delegation_limit:{active_subagents}>{budget.max_active_subagents}"
        )
    return {
        "status": "attention" if alerts else "within_budget",
        "session_count": session_count,
        "active_subagents": active_subagents,
        "totals": totals,
        "by_source": dict(sorted(by_source.items())),
        "alerts": sorted(alerts),
    }
