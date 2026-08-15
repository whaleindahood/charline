# Usage budgets

Hermes remains the usage source of truth. `scripts/usage_report.py` reads aggregate counters from the existing Hermes state database and creates no second store.

## Default guardrails

- maximum two active subagents;
- no duplicate worker goal while the first worker is active;
- one retry only after the prior worker has ended and its evidence was inspected;
- rotate or compact a session at 120 messages;
- review a session at 300 API calls;
- rotate a session at 250,000 fresh input tokens;
- rotate a session at 5,000,000 cache-read tokens;
- delegate only independent workstreams with non-overlapping file ownership.

These thresholds are operational warnings, not provider quota calculations. Fresh input, output and cache-read tokens stay separate because subscription limits may weight them differently.

## Response

When a threshold is reached: finish the current safe atomic step, record durable facts/artifacts, start a fresh session, and do not copy unrelated conversation history. When delegation cap is reached, wait for one active worker to finish before launching another. Use Hermes Kanban only when pending work must survive a restart.
