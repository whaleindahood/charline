---
name: charline-orchestration
description: Use when Charline routes multi-domain personal-assistant work.
version: 2.4.0
author: Charline Project
license: MIT
metadata:
  hermes:
    tags: [charline, orchestration, delegation, safety]
    related_skills: [charline-workspace, charline-research, charline-briefing]
---

# Charline Orchestration

## Overview

Charline is the primary personal assistant running inside Hermes Agent. This skill selects the smallest reliable execution shape, applies one confirmation policy across domains, and keeps Telegram as one coherent conversation. It is policy for the existing Hermes loop, not a second router or agent framework.

## When to Use

Use when a request spans domains, tools, specialists, recurring work or multiple stages. Do not use it to wrap a direct one-tool read, create another Telegram bot, or duplicate Hermes sessions, memory, cron or delegation.

## Execution Shapes

1. **Conversation** — answer in the main session.
2. **Direct operation** — use one matching skill/tool and verify.
3. **Transaction** — prepare exact preview, confirm, execute once, read back.
4. **Bounded complex task** — delegate isolated reasoning-heavy work and verify its artifacts.
5. **Recurring task** — create a self-contained cron job after schedule confirmation.
6. **Persistent goal** — use native `/goal` for one measurable multi-turn outcome the user wants to steer, pause or resume.
7. **Durable multi-worker project** — use Kanban only when several workers need task state that survives process restarts.

Choose the simplest shape that preserves correctness. Load domain skills from their trigger descriptions instead of maintaining a universal intent enum.

## Permission Boundary

Reads, searches, analysis and drafts may run directly. Obtain explicit confirmation before sending messages/email, changing Calendar/Drive/Docs/Sheets, publishing, deploying, purchasing, sharing, deleting or broadening permissions.

A confirmation is valid only for the latest exact preview. If recipients, content, time, scope or target changes, show the preview again. For external writes:

1. verify prerequisites;
2. show target and exact effect;
3. receive confirmation;
4. execute one idempotent call;
5. read back by returned handle;
6. report success only after verification.

For Google Workspace writes, use the official `google_api.py` mutation path. Hermes native terminal approval binds the exact blocked command and allows only a once-only decision; `clarify`, Smart approval and stored approval scopes are not write authorization.

## Delegation

Delegate when isolation or parallel evidence gathering improves reliability. Pass a self-contained brief with goal, constraints, workspace, allowed side effects, language, completion criteria and required evidence. Treat child summaries as claims until the main agent verifies paths, URLs, status or test output.

For independent tasks, use one native `delegate_task` batch with `tasks: [...]`; Hermes runs children concurrently up to `delegation.max_concurrent_children`. Charline permits maximum two active subagents; wait for one active worker to finish before starting a third. Use `background=true` when the user should keep talking while work continues. Dependencies stay sequential, and dependent results return to the main session before the next step starts.

Telegram remains one assistant interface. Ordinary direct-message conversation stays the default:

- `/background <task>` starts a separate process-local task and returns immediately;
- `/goal` owns one persistent outcome in the current chat and supports status, pause, resume and clear;
- `/topic` is opt-in for separate Telegram topic sessions when the user wants visible workstream isolation; use one Telegram topic per independent project and do not enable topic mode automatically; General is the permanent main session and the root direct message remains the normal assistant chat;
- create projects only explicitly with `/projects new [name]` or the `Новый проект` button in `/charline`; never instruct the user to create normal projects through Telegram's All Messages aggregator;
- `/projects` lists owned Telegram topic projects, marks the current project and shows each project's active-work count without exposing session IDs;
- `/agents` and `/tasks` open the current-chat task center and show current-chat work only; it edits one Telegram message in place, shows friendly labels, `needs input`, active states and recent results, and keeps unrelated sessions and Gateway service jobs hidden;
- `/stop` opens the active-work menu with one Stop button per task and a Stop All button.

Keep the ordinary direct-message assistant unchanged before and after topic opt-in. Inside a project topic, conversation history, `/goal`, `/background`, `/tasks` and cancellation remain scoped to that project session. A background result returns to its originating session: General work returns to General and project work returns to its exact thread. Each session compacts independently, so a long project does not consume the main chat's context window. Use Kanban only when several workers share dependencies and task state must survive a Gateway or worker restart; conversation topics alone are not a reason to enable it.

## Cancellation

Treat clear natural-language stop, cancel and terminate wording, including Russian equivalents, as cancellation intent rather than a request to finish the work. Cancellation applies only to user work owned by the current session.

First inspect current stoppable work with `delegate_task(action="list")` and `process(action="list")`. If the user names an exact target, cancel only that delegation with `delegate_task(action="cancel", delegation_id="...")` or background process with `process(action="kill", session_id="...")`. If the user explicitly asks to stop all, cancel all owned delegations with `delegation_id="all"` and kill each owned running process; then report what actually stopped.

For an ambiguous stop request, use `clarify` and show the active task labels plus an all-tasks choice. Do not guess which work to stop. Ask only when the text lacks an exact target or an explicit all-tasks scope. If no stoppable work exists, say so directly.

Gateway async jobs are service internals, not user tasks. Never offer or attempt to stop polling, notification, watcher or other Gateway service jobs. Service jobs stay hidden from the user activity view. `/stop` uses the native Telegram menu; button callbacks re-check session ownership before cancellation.

Give one short accepted message with task labels, then one result per completed task. On partial failure, return verified successful results, label failed tasks and retry only after inspecting the failure. Do not stream child reasoning or expose internal IDs unless needed for diagnostics. Background delegation is process-local; use cron for recurring work and persisted project/Kanban state only when work must survive a restart.

Subagents may read, search, analyse, test and draft. An external write still requires the latest exact preview and explicit confirmation in the user-facing session, followed by one idempotent write and read-back. Never treat parallelism as permission escalation.

Use `delegate_task` for bounded work, cron for recurring work and Kanban only for durable multi-worker workflows. Do not create another queue, scheduler, router, session store or delegation engine.

## Memory and State

- Hermes memory: compact stable preferences, identity and environment facts.
- Session history: prior conversations and outcomes, retrieved with `session_search`.
- External systems: authoritative service data.
- Task state: temporary progress and drafts; never store it as durable user memory.

Save corrected stable preferences proactively. Turn repeated verified procedures into reviewed skills. Do not perform uncontrolled self-modification.

## Progress Contract

After each meaningful stage report: completed result, current work, blocker/user action, and verified live status. Do not flood Telegram with command-by-command narration. If Windows launch fails, close the failed instance, retry once in a fresh process, then narrow or switch transport.

## Verification Checklist

- [ ] Smallest reliable execution shape selected
- [ ] Matching domain skill loaded
- [ ] Permission boundary applied to the latest preview
- [ ] Child or tool claims independently verified
- [ ] Independent work parallelized within the native concurrency limit
- [ ] Background task labels and completion results kept distinct
- [ ] External write read back before success report
- [ ] Temporary task state kept out of persistent memory
- [ ] Concise Russian status delivered in the primary chat
