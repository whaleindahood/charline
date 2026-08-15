# Project rules

## Architecture invariants

1. Hermes Agent is the only agent runtime and the only Telegram polling owner.
2. Do not implement a second router, memory store, scheduler, session system, delegation engine or general tool registry.
3. Domain code must be deterministic and independently testable.
4. Skills contain policy and procedure; scripts contain bounded deterministic work.
5. Google Workspace is the source of truth for Google data. Do not mirror it locally.
6. Mini App, tunnel and reverse-proxy code are outside V1.

## Safety

- Read/search/analyse/draft operations may run directly.
- Email/message sending, calendar/Drive/Docs/Sheets writes, publication, deployment, destructive operations and permission changes require explicit confirmation.
- After an external write, verify via API read-back before reporting success.
- Retries of writes must be idempotent or preceded by a narrow read to determine the prior outcome.
- Never read, print, copy or commit credential values.

## Engineering

- Use Ponytail `full` for coding sessions and run `ponytail-review` before handoff.
- Use strict RED-GREEN-REFACTOR for behavior changes.
- Keep the project as a standalone Git repository.
- Run focused tests, then the full suite.
- Verify actual runtime state before claiming a service works.
- Use delegation for bounded independent reasoning; use cron for recurring work; introduce Kanban only for durable multi-worker workflows.
