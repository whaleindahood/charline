---
name: charline
description: Show Charline's user-facing capability menu and examples. Use when the user invokes /charline, asks what Charline can do, requests the assistant menu, or needs help phrasing a task.
---

# Charline

## Overview

Present one concise Russian navigation view over the existing Hermes Agent. This is a discoverability skill, not an execution layer.

## When to Use

Use for `/charline`, "покажи меню", "что ты умеешь", onboarding and task examples. Ordinary requests should go directly to the matching domain skill without opening this menu first.

## Capability Menu

Return a short list with natural language examples:

- Calendar — agenda, availability and confirmed event creation: `Назначь встречу 9 августа в 13:00`.
- Mail — search, summarize, draft and confirmed send: `Найди важные непрочитанные письма`.
- Reminders and briefings — confirmed one-time or recurring Hermes cron work: `Напомни завтра оплатить счёт`.
- Workspace — Drive, Docs, Sheets and Contacts: `Найди документ с планом проекта`.
- Research — sourced analysis with bounded delegation: `Сравни три варианта и приведи источники`.
- Projects — `/projects` lists isolated Telegram topic projects and their active work; `/topic` remains explicit opt-in: `Создай отдельный проект для ремонта и веди задачи там`.
- Task control — `/tasks` opens the current-chat task center with refresh and scoped stop controls; ordinary cancellation wording remains supported.
- Developer work — repository analysis, tests and confirmed deployment: `Проверь проект и предложи исправления`.

Finish with: "Напишите или надиктуйте задачу обычными словами." Mention `/commands` as the complete technical Hermes command catalog only when the user asks about commands or administration.

## Telegram Presentation

Use normal Markdown headings, lists and links. Use Markdown tables only for compact comparisons or state snapshots with few short columns. Telegram Rich Messages render those tables when enabled; fall back to lists automatically on unsupported clients. Never force tables into narrow task controls: `/tasks` uses one editable native message with inline buttons.

## Native Hermes Boundary

Accept natural language and voice through the existing Hermes Gateway. After the user chooses or states a task, load the matching domain skill and follow `charline-orchestration`. Use Hermes sessions/topics, Memory, `clarify`, `delegate_task`, `/background`, cron and project surfaces directly.

This skill does not implement a router, command dispatcher, Telegram handler, session store, scheduler, memory store or tool registry. It does not perform external writes, source reads or background work merely to display the menu.

## Verification Checklist

- [ ] Response is concise and in Russian
- [ ] Examples use ordinary user language rather than requiring slash commands
- [ ] `/commands` remains the route to the complete Hermes catalog
- [ ] No tools, external writes or duplicated Hermes infrastructure used
