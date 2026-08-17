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
- Projects — a message from All Messages starts an isolated Telegram topic automatically; `/projects new [name]` creates a named project: `Создай отдельный проект для ремонта и веди задачи там`.
- Task control — `/tasks` opens the current-chat task center with refresh and scoped stop controls; ordinary cancellation wording remains supported.
- Developer work — repository analysis, tests and confirmed deployment: `Проверь проект и предложи исправления`.

Finish with: "Напишите или надиктуйте задачу обычными словами." Mention `/commands` as the complete technical Hermes command catalog only when the user asks about commands or administration.

## Telegram Presentation

Use normal Markdown headings, lists and links. Use Markdown tables only for compact comparisons or state snapshots with few short columns. Telegram Rich Messages render those tables when enabled; fall back to lists automatically on unsupported clients. Never force tables into narrow task controls: `/tasks` uses one editable native message with inline buttons.

## Native Telegram Panel

On Telegram, `/charline` uses native Telegram inline buttons in one editable card:

- `Сегодня` performs concurrent read-only Calendar and Gmail reads and combines them with active work, pending decisions and upcoming Hermes schedules. Partial source failure must remain visible instead of hiding the available sections.
- `Календарь`, `Почта` and `Файлы` perform bounded useful read views; writes and searches needing user input continue through ordinary conversation and normal confirmation.
- `Задачи` opens the existing task center scoped to the current topic; project overview may aggregate only the caller's owned sessions.
- `Проекты` opens a native owned-project card with active-work counts and scoped `Сводка`/`Задачи` actions. Telegram's own topic list remains the navigation surface; do not invent web deep links.
- `Расписания` opens the existing Hermes cron jobs with refresh, pause, resume, run-now and durable execution history; creation remains conversational.
- `Память` reads the existing Hermes `USER.md`/`MEMORY.md` entries and offers owner-bound two-step deletion with read-back. The store has no per-entry timestamps; do not fabricate dates. `Сервисы` shows connector presence without reading credential values.
- `Исследование` exposes sourced analysis without creating another delegation engine.
- `Новая задача` asks the user to write or dictate the request normally.
- `Новый проект` creates one named isolated Telegram topic and Hermes session; All Messages remains the native shortcut for an automatic new conversation.
- `Все функции Hermes` opens the existing paginated `/commands` catalog with native `←`/`→` buttons that edit one Telegram message, so advanced capabilities remain available without crowding the home card.

Category details and `Назад` edit the same card. Input-requiring actions use Telegram `ForceReply`; the reply remains an ordinary Hermes message in the same topic session, so it keeps normal skills, context and confirmation rules. Read-only cards may fetch current Google data; no category click performs an external write.

The home card identifies scope from the current Telegram thread and shows its title. A brand-new thread keeps its own session and is never merged into an older topic.

On Gateway startup, restore Telegram's native command menu so a stale Web App button cannot keep opening an obsolete tunnel.

## Native Hermes Boundary

Accept natural language and voice through the existing Hermes Gateway. After the user chooses or states a task, load the matching domain skill and follow `charline-orchestration`. Use Hermes sessions/topics, Memory, `clarify`, `delegate_task`, `/background`, cron and project surfaces directly.

This skill does not implement a router, command dispatcher, Telegram handler, session store, scheduler, memory store or tool registry. It does not perform external writes, source reads or background work merely to display the menu.

## Verification Checklist

- [ ] Response is concise and in Russian
- [ ] Examples use ordinary user language rather than requiring slash commands
- [ ] `/commands` remains the route to the complete Hermes catalog
- [ ] No tools, external writes or duplicated Hermes infrastructure used
