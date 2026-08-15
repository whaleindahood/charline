# Charline roadmap

Charline is a general personal assistant implemented as policy plus deterministic helpers inside Hermes Agent. Calendar is one capability, not the product boundary.

## Definition of V1

V1 includes phases 0–5 below. A phase is code-complete only when its deterministic behavior, policy skill, focused tests and product evals are present. It is production-verified only after the separate live gates in `ACCEPTANCE.md` pass. External effects always retain per-operation confirmation; “release complete” never grants blanket write permission.

## Status

| Phase | Repository | Live proof |
|---|---|---|
| 0. Foundation | Complete | Profile synced; Hermes 0.20, fixed SQLite, OAuth, one Gateway, Telegram polling and round trip verified |
| 1. Calendar | Complete | Authenticated read and confirmed create/read-back/delete/absence sandbox proof passed |
| 2. Workspace | Complete within installed Google CLI surface | Gmail, Drive and Contacts reads passed; confirmed Gmail self-send, Docs append and Sheets update read-back passed |
| 3. Research | Complete | Browser provider available; optional structured web provider is not configured |
| 4. Briefing/reminders | Complete | Confirmed cron create/read-back/run, user-observed delivery and separately confirmed cleanup passed |
| 5. Developer/usage | Complete | Deployment remains separately confirmed |
| 6. Native conversational UX | Complete | Native `/charline` panel implemented; activation plus `/projects`, recent task results and labelled confirmation buttons require final live proof |

## Phase 0 — Foundation

Exit criteria: standalone recoverable Git history; manifest-backed skill sync/restore; explicit content trust boundaries; transaction state machine; usage report; runtime diagnostics; focused and full tests.

## Phase 1 — Calendar vertical slice

Exit criteria: agenda/availability policy; deterministic timezone, conflict, buffer and slot planning; exact preview and once-only approval of the immutable `google_api.py` command; unknown-outcome reconciliation; read-back contract; eval coverage.

Installed Google interface limitation: Calendar supports list/create/delete, but not get-by-ID, update or free/busy. Update requests remain drafts. Create verification uses a narrow list and returned event ID.

## Phase 2 — Gmail, Drive and documents

Exit criteria: Gmail, Drive, Docs and Sheets domain skills; reads direct; writes use the common transaction contract; cross-service authorization does not leak; unavailable verification blocks unsafe effects.

Installed-interface limitations are explicit in `RELEASE.md`. In particular, Drive share/delete stays draft-only because current permission/trash read-back is insufficient.

## Phase 3 — Research and knowledge work

Exit criteria: current source policy; primary-source priority; prompt-injection boundary; facts/inference/uncertainty separation; URL validation; no more than two independent workers; deterministic evidence normalization.

## Phase 4 — Briefing, reminders and recurring work

Exit criteria: deterministic partial-failure brief; conflict/overdue detection; self-contained reminder draft; timezone and schedule validation; idempotency key; Hermes cron is the only scheduler; exact confirmation and read-back policy.

## Phase 5 — Developer and extended capabilities

Exit criteria: RED–GREEN–REFACTOR workflow; architecture guard against a second runtime/service SDKs; focused/full test gates; separate usage counters and budgets; bounded delegation; release and evidence procedures.

## Phase 6 — Native conversational UX

Goal: make the existing Hermes chat the complete assistant interface. Natural language and voice must reach the same domain skills without a second router, session system or Mini App.

Exit criteria: `/charline` is visible in the Telegram menu; ordinary text and Russian voice scheduling request only missing blocking details, then silently check availability in one initial Calendar read before one confirmation preview; conflicts return the nearest available alternative; changed drafts invalidate prior confirmation; confirmed writes are read back; `/topic` and `/background` demonstrate independent work without blocking the main chat; `/projects` lists isolated topic projects; `/tasks` (`/agents`) edits one current-chat task card in place with refresh, `needs input`, recent results and scoped stop controls while hiding Gateway service jobs; compact Markdown tables use Telegram Rich Messages; Workspace confirmation uses once-only native terminal approval for the exact `google_api.py` write command; natural-language cancellation and `/stop` provide scoped task controls; the live checks in `ACCEPTANCE.md` pass and receive new evidence.

## Post-V1, opt-in only

- Additional services through narrow least-privileged skills.
- Durable multi-worker Kanban only when several workers share dependencies and their task state must survive Gateway/worker restarts; ordinary parallel requests and separate project chats do not qualify.
- Mini App, tunnel, reverse proxy or custom web client.

Permanently excluded: a second agent runtime, scheduler, memory store, session system, delegation engine, universal router or autonomous unconfirmed external writes.
