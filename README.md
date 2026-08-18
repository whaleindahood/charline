# Charline

Charline is the owner's personal ChatGPT plus Codex/Claude Code experience in Telegram, implemented as a thin product layer over Hermes Agent.

## Current status

V1 repository surface is implemented, including Phase 6 conversational UX behavior. The 2026-08-07 production evidence is historical; fresh text, voice, menu and parallel-work evidence is still required before calling the current profile production-verified. Future external writes still require a fresh exact preview and explicit confirmation.

Repository completion and deployment to the active profile remain separate, reviewable operations even after production verification.

## Product contract

The normative product definition is [`docs/PRODUCT.md`](docs/PRODUCT.md).

- One existing Telegram bot and one permanent Main conversation in the root DM.
- Hermes Agent owns the model loop, Telegram Gateway, sessions, memory, skills, cron and delegation.
- Projects are native Telegram Private Chat Topics. Their `chat_id + thread_id` routes through ordinary Hermes sessions; Charline has no project/session database or last-project router.
- Background tasks are bounded Hermes delegation inside Main or a project. They do not create projects and return to their originating conversation.
- Google Workspace, research, reminders, documents and developer workflows are domain capabilities loaded on demand.
- Reads may run directly. External writes require an exact preview and explicit confirmation, followed by read-back verification.
- Mini Apps are excluded from V1 and may return only as optional visual clients.

## Repository layout

- `docs/` — architecture, security and operating procedures.
- `skills/` — version-controlled Charline policy and domain skills.
- `plugins/charline/` — contextual `/charline`, `/today`, `/projects`, `/tasks`, `/schedules`, `/settings` views and the model-callable project tool.
- `src/charline/` — deterministic helpers only; no agent runtime.
- `evals/` — product-level regression scenarios.
- `scripts/` — reproducible install, health and backup operations.
- `tests/` — executable tests.

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for scope and [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) for release gates.

## Development

```powershell
uv sync --group dev
python -m pytest -q
python scripts/run_evals.py
```

The active Hermes profile remains the current `default` profile. This repository is the source of truth for Charline-owned artifacts; secrets and Hermes runtime state never belong here.

Charline projects require Telegram Threaded Mode and Hermes `dm_topics`; they do not require or automatically enable the separate upstream `/topic` multi-session mode. Keep `ignore_root_dm: false` so Main remains conversational. See [`docs/MIGRATION.md`](docs/MIGRATION.md) for the explicit live-profile migration.

The Telegram picker contains Today, Projects, personal Tasks, Schedules and Settings. Calendar, mail, files, research and developer work remain available through ordinary text or voice; `/commands` remains the manually callable power-user catalog.
