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

The persistent Telegram menu is limited to five daily entry points: Today, Projects, Tasks, Schedules and Settings. Conversation remains primary: Calendar, Mail, Files, Research and Memory intents are requested by text or voice. `/commands` remains manually available as the complete technical Hermes catalog but is not daily navigation.

Telegram is the primary daily interface. The root DM is a permanent conversational Main session. A project is a native Telegram Private Chat Topic: `chat_id + thread_id` flows through Hermes' normal session-key builder, giving every project isolated history and compaction. Charline never redirects a root message to the last project and has no project/session database. The separate upstream `/topic` multi-session feature may remain available to advanced users, but Charline neither enables nor requires it; `ignore_root_dm` stays false.

`/charline`, `/today`, `/projects`, `/schedules` and `/settings` are supplied by the Charline Hermes plugin. `/tasks` is rewritten by explicit Telegram menu configuration to the same plugin Task Center while `/agents` remains the upstream diagnostic command. Main `/charline` renders a small daily status card; inside a configured native project topic it renders exact-topic status and actions. Read navigation uses compact callback actions reconstructed from callback chat/thread plus Hermes-owned state, so no UI database or expiring closure is needed. Mutations retain short-lived owner/chat/thread-bound confirmations.

`/projects new <name>`, the `Новый проект` action and the model-facing project tool share one service over the capability-gated `ensure_private_topic` platform action. Hermes' Telegram adapter creates the topic, obtains the real `thread_id`, and persists it in `platforms.telegram.extra.dm_topics`. `/projects` and project summaries are read-only metadata views; they never inject summary prompts into project transcripts.

Hermes continues to own delegation, `/background`, `/tasks` (`/agents`), `/stop`, `/goal`, cron, Memory and session search. Background work and cron delivery retain the exact origin Main/topic routing. Each session compacts independently. Global Memory stores durable cross-session preferences and facts, not transient project progress; project details stay in the project session and authoritative artifacts. Rich Messages render compact Markdown tables; external Workspace writes retain exact preview, explicit confirmation, one write and read-back verification. Mini Apps remain outside V1.

V1 deliberately does not rename, delete or archive project topics: current Hermes can rename a thread but does not atomically synchronize that rename with configured `dm_topics`, and Telegram topic deletion is separate from Hermes history deletion. History is therefore never silently removed. If durable structured project state is later proven necessary, prefer an optional reviewed `PROJECT.md` artifact; do not add another memory database.

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
