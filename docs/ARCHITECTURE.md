# Charline architecture

## Decision

Charline is the user's product identity and policy layer on top of Hermes Agent. The active Hermes `default` profile remains the production identity to preserve the existing Telegram route, memory and sessions.

Hermes, not Charline code, interprets natural-language requests and decides which tools, clarifications, agents and execution shape are needed. Charline must not add an intent router or scripted question tree. The product behavior is defined in [`PRODUCT.md`](PRODUCT.md).

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
  |-- durable cron schedules
  `-- native Kanban for restart-safe project execution
```

## State boundaries

1. Hermes memory: compact durable preferences and facts.
2. Session store: conversation history and retrieval.
3. External systems: Google Workspace and other authoritative services.
4. Hermes Kanban: durable project execution state, dependencies, handoffs, review and restart recovery.

## Domain modules

Initial V1 capabilities:

- orchestration and permission policy;
- Google Workspace: Calendar, Gmail, Drive, Docs and Sheets;
- sourced research with bounded parallel delegation;
- read-only daily briefings and confirmed reminders;
- deterministic calendar free-slot planning;
- developer workflows through existing Hermes skills.

The daily command-center renderer is deterministic and ephemeral. It ranks conflicts, overdue commitments and unavailable sources first, limits ordinary detail per source, retains authoritative handles and reports observation freshness. It does not persist a cross-source snapshot or expose raw tool/alert output.

## Interfaces

The persistent Telegram menu contains five owner-facing views: Today, Projects, Tasks, Schedules and Settings. Conversation remains primary: Calendar, Mail, Files, Research and developer work are requested by text or voice rather than exposed as one button per integration. `/commands` remains manually available as the complete technical Hermes catalog but is not daily navigation.

Telegram is the primary daily interface. The root DM is a permanent conversational Main session. A project is a native Telegram Private Chat Topic: `chat_id + thread_id` flows through Hermes' normal session-key builder, giving every project isolated history and compaction. Charline never redirects a root message to the last project and has no project/session database. The separate upstream `/topic` multi-session feature may remain available to advanced users, but Charline neither enables nor requires it; `ignore_root_dm` stays false.

`/today`, `/projects`, `/tasks`, `/schedules` and `/settings` are the daily Telegram command menu. `/today` dispatches a normal Hermes turn in the exact chat so the model can synthesize live connected sources. `/tasks` is rewritten by explicit Telegram configuration from upstream's technical task command to Charline's personal-task view; upstream diagnostics remain available through advanced commands. Personal tasks are compact native Memory entries with a stable `Задача: ` prefix, not agent processes. Read navigation uses compact callback actions reconstructed from callback chat/thread plus Hermes-owned state, so no UI database is introduced. Mutations retain short-lived owner/chat/thread-bound confirmations.

`/projects new <name>` creates an empty native topic when explicitly requested. For a natural substantial request, the async `charline_projects(start)` tool uses the capability-gated `start_private_topic_task` action: Hermes' Telegram adapter creates or reuses the topic, persists its real `thread_id`, then dispatches the complete original request through the normal agent path in that topic. Durable multi-stage work can immediately use native Kanban with the project request ID as its idempotency key. `/projects` remains a read-only metadata view.

Hermes continues to own delegation, `/background`, technical task diagnostics, `/stop`, `/goal`, cron, Kanban, Memory and session search. Background work, Kanban notifications and cron delivery retain the exact origin Main/topic routing. Each session compacts independently. Global Memory stores durable cross-session preferences, facts and compact owner-requested personal tasks, not transient project progress; project details stay in the project session, native Kanban and authoritative artifacts. Rich Messages render compact Markdown tables; external Workspace writes retain exact preview, explicit confirmation, one write and read-back verification. Mini Apps remain outside V1.

V1 deliberately does not rename, delete or archive project topics: current Hermes can rename a thread but does not atomically synchronize that rename with configured `dm_topics`, and Telegram topic deletion is separate from Hermes history deletion. History is therefore never silently removed. A topic is not bound one-to-one to a repository; the model chooses or asks for a workspace, and several topics may use the same folder.

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
