---
name: charline-orchestration
description: Use when Charline routes multi-domain personal-assistant work.
version: 2.0.0
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
6. **Durable project** — use persisted task state or Kanban only when work must survive process restarts.

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

## Delegation

Delegate when isolation or parallel evidence gathering improves reliability. Pass a self-contained brief with goal, constraints, workspace, allowed side effects, language, completion criteria and required evidence. Treat child summaries as claims until the main agent verifies paths, URLs, status or test output.

Use `delegate_task` for bounded work, cron for recurring work and Kanban only for durable multi-worker workflows. Do not expose subagent sessions or IDs to the user unless they are needed for diagnostics.

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
- [ ] External write read back before success report
- [ ] Temporary task state kept out of persistent memory
- [ ] Concise Russian status delivered in the primary chat
