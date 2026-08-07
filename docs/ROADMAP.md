# Charline roadmap

Charline is a general personal assistant built as a policy and capability layer inside Hermes Agent. Calendar is one capability, not the product boundary.

## Release gates

Every phase requires focused tests, the full repository suite and verified runtime evidence appropriate to that phase. External writes remain disabled until preview, confirmation, idempotency and read-back behavior passes in a test account.

## Phase 0 — Foundation

- recoverable Git history and isolated worker branches/worktrees;
- safe skill install, verification and rollback;
- explicit trust boundaries for Telegram, web and Google content;
- honest health reporting and token/use observability;
- stable Hermes Gateway and profile backup/restore.

## Phase 1 — Calendar vertical slice

- agenda and availability reads from Google Calendar;
- deterministic timezone, conflict, buffer and free-slot planning;
- exact event preview, explicit confirmation, one idempotent write and read-back;
- sandbox integration tests before production calendar writes.

## Phase 2 — Gmail, Drive and documents

- Gmail search, summaries and drafts;
- confirmed email sending with recipient/content verification;
- Drive search, organization and confirmed sharing;
- Docs and Sheets read/draft workflows, then confirmed writes;
- cross-service flows such as email evidence to calendar draft without implicit authorization.

## Phase 3 — Research and knowledge work

- current multi-source research with citations;
- bounded delegation only for independent workstreams;
- comparison, synthesis and decision support;
- reusable reviewed procedures in skills, not a second memory or routing system.

## Phase 4 — Briefing, reminders and recurring work

- read-only morning and weekly briefing;
- confirmed reminders and self-contained cron jobs;
- per-source failure reporting and duplicate-delivery protection;
- restore and restart tests for scheduled work.

## Phase 5 — Developer and extended capabilities

- repository inspection, coding, testing and review workflows;
- optional additional services through narrow skills and least-privileged tools;
- usage budgets, context rotation and delegation limits;
- Kanban only for durable multi-worker workflows proven to need it.

## Deferred

- Mini App, tunnel, reverse proxy and custom web shell;
- custom agent runtime, scheduler, memory store or universal router;
- autonomous external writes without an exact confirmed preview.
