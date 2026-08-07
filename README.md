# Charline

Charline is a Hermes-native general personal assistant configuration, not a second agent framework or only a calendar bot.

## Current status

This repository is the V1 foundation and is not end-to-end ready. Policy, deterministic helpers and operational controls are being stabilized before live Workspace writes or recurring automation are enabled.

## Product contract

- One existing Telegram bot and one primary conversational chat.
- Hermes Agent owns the model loop, Telegram Gateway, sessions, memory, skills, cron and delegation.
- Google Workspace, research, reminders, documents and developer workflows are domain capabilities loaded on demand.
- Reads may run directly. External writes require an exact preview and explicit confirmation, followed by read-back verification.
- Mini Apps are excluded from V1 and may return only as optional visual clients.

## Repository layout

- `docs/` — architecture, security and operating procedures.
- `skills/` — version-controlled Charline policy and domain skills.
- `src/charline/` — deterministic helpers only; no agent runtime.
- `evals/` — product-level regression scenarios.
- `scripts/` — reproducible install, health and backup operations.
- `tests/` — executable tests.

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for capability order and release gates.

## Development

```bash
python -m unittest discover -s tests -v
```

The active Hermes profile remains the current `default` profile. This repository is the source of truth for Charline-owned artifacts; secrets and Hermes runtime state never belong here.
