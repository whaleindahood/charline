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

Telegram is the primary daily interface. General is the permanent main assistant session before and after `/topic` opt-in. `/charline` is a thin native control surface over existing Hermes sessions, delegation, cron, Memory and tools: `Сегодня` aggregates bounded Google reads, active work, pending decisions and upcoming schedules; `Расписания` controls Hermes cron jobs; project cards route summaries and task controls to the exact project session; Memory cards read and update the existing Hermes files with confirmation and read-back. Input-requiring buttons use Telegram ForceReply and re-enter the ordinary Hermes conversation instead of a second intent router. Natural-language background requests or `/background` run bounded work while the chat stays responsive; results return to the originating General or project session. From General, `/tasks` (`/agents`) aggregates the caller's main and owned project sessions; within a project it remains scoped to that project. The editable card shows active states, `needs input`, recent delegation results, refresh and ownership-checked stop controls while hiding Gateway service jobs. Natural-language cancellation works during an active turn; `/stop` provides per-task and stop-all controls. Native `/goal` owns one steerable multi-turn outcome. Each explicitly created project topic has its own Hermes session and compacts independently; `/projects new [name]` or `Новый проект` creates one, while `/projects` lists owned projects and active-work counts. Rich Messages render compact Markdown tables in ordinary answers; Rich Drafts provide provisional streaming only. Workspace writes use a Rich Message preview followed by Hermes native once-only terminal approval for the exact blocked `google_api.py` command. Hermes Desktop/Dashboard is the expanded operational console. Mini Apps are excluded from V1 and cannot become a critical path.

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
