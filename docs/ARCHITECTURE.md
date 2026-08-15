# Charline architecture

## Decision

Charline is the user's product identity and policy layer on top of Hermes Agent. The active Hermes `default` profile remains the production identity to preserve the existing Telegram route, memory and sessions.

## Runtime

```text
Telegram / Hermes Desktop
          |
          v
Hermes Gateway (single Telegram owner)
          |
          v
Main Charline session
  |-- USER.md / MEMORY.md
  |-- session history + session_search
  |-- Charline orchestration policy
  |-- domain skills
  |-- built-in tools + Google Workspace
  |-- bounded delegate_task workers
  |-- durable cron automation
  `-- optional Kanban after demonstrated need
```

## State boundaries

1. Hermes memory: compact durable preferences and facts.
2. Session store: conversation history and retrieval.
3. External systems: Google Workspace and other authoritative services.
4. Structured workflow state: only when a real workflow cannot use an external source of truth; schema and lifecycle must be explicit.

## Domain modules

Initial V1 capabilities:

- orchestration and permission policy;
- Google Workspace: Calendar, Gmail, Drive, Docs and Sheets;
- sourced research with bounded parallel delegation;
- read-only daily briefings and confirmed reminders;
- deterministic calendar free-slot planning;
- developer workflows through existing Hermes skills.

## Interfaces

Telegram is the primary daily interface. Ordinary direct-message conversation is the default. Natural-language background requests or `/background` run bounded work while the chat stays responsive; `/tasks` (`/agents`) opens one editable current-chat task card with active states, `needs input`, recent delegation results, refresh and scoped stop controls while hiding Gateway service jobs. Natural-language cancellation works during an active turn; `/stop` provides per-task and stop-all controls. Native `/goal` owns one steerable multi-turn outcome. `/topic` is opt-in: one Telegram topic becomes one independent project session and the root direct message becomes the lobby only after opt-in; `/projects` lists those owned topic projects and their active-work counts. Rich Messages render compact Markdown tables in ordinary answers; Rich Drafts provide provisional streaming only. Workspace writes use a Rich Message preview followed by Hermes native once-only terminal approval for the exact blocked `google_api.py` command. Hermes Desktop/Dashboard is the expanded operational console. Mini Apps are excluded from V1 and cannot become a critical path.

## Deployment

V1 runs on the existing Hermes Gateway. No Pinggy, Cloudflare Worker or custom FastAPI backend is required. A future always-on host should run the same Hermes profile with controlled backup/restore and one Gateway instance.

## Non-goals

- second bot or Gateway;
- custom LLM/tool loop;
- custom Google OAuth/API abstraction;
- broad autonomous writes;
- multi-agent swarm without a durable task model;
- custom web shell before the native Hermes surfaces are proven insufficient.

Capability sequencing and release gates are defined in [`ROADMAP.md`](ROADMAP.md).
