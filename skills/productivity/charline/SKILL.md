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
- Projects — substantial artifact work is moved with its complete original request into a native Telegram topic and starts there immediately: `Создай сайт для моего бизнеса`.
- Personal tasks — `/tasks` shows the owner's remembered actions, not agents or shell processes: `Запомни, мне нужно сделать лабораторную`.
- Active project work — Hermes reports progress, blockers and verified results in the project topic; native Kanban is used when durable stages or workers must survive a restart.
- Developer work — repository analysis, tests and confirmed deployment: `Проверь проект и предложи исправления`.

Finish with: "Напишите или надиктуйте задачу обычными словами." Mention `/commands` as the complete technical Hermes command catalog only when the user asks about commands or administration.

## Telegram Presentation

Use normal Markdown headings, lists and links. Use Markdown tables only for compact comparisons or state snapshots with few short columns. Telegram Rich Messages render those tables when enabled; fall back to lists automatically on unsupported clients. Never force tables into narrow task controls: `/tasks` uses one editable native message with inline buttons.

## Native Telegram Panel

The persistent daily menu exposes only `Сегодня`, `Проекты`, `Задачи` and `Настройки`. `/commands` remains manually available. Hidden technical commands and domain capabilities are not disabled. Cron is managed conversationally; useful upcoming reminders may appear in `Сегодня`, but there is no Charline schedules administration view.

In Main, `/charline` invites ordinary text or voice. Its compact card links to Projects, personal Tasks and Settings; `Сегодня` is a compact live state view. Calendar, Mail, Files, Research and recurring work remain natural-language intents rather than one button per integration. In a configured project topic, normal text continues that project's Hermes session.

Do not expose raw Memory records, process/delegation IDs, cron administration, model/provider plumbing or internal worker controls in the daily UI. Describe progress and blockers in user language. Advanced Hermes commands remain available when the owner explicitly requests diagnostics.

When the owner asks to remember an actionable personal task, use native Hermes Memory with one exact entry prefixed `Задача: `. The model decides the useful wording; do not select from a coded intent list or question tree. A due-time reminder is a separate native Hermes cron job when requested or clearly implied. `/tasks` filters only these entries and completion removes the exact entry after confirmation.

Read-only cards are reconstructed from callback chat/thread and Hermes-owned state and edit the same Telegram message. They do not rely on a menu closure or inject administrative messages into a project transcript. Stop-all, cron deletion, memory deletion and external writes retain short-lived explicit confirmations.

The root DM is permanent Main. Ordinary questions and small operations stay there. When durable context or substantial artifact work is useful, call `charline_projects(action="start", name=..., task=...)` once with the owner's complete request; the native topic is created/reused and Hermes starts the task inside it. A project topic keeps its own ordinary Hermes session and is never merged into Main or another project. A topic is not a repository: several topics may use the same workspace.

On Gateway startup, restore Telegram's native command menu so a stale Web App button cannot keep opening an obsolete tunnel.

## Native Hermes Boundary

Accept natural language and voice through the existing Hermes Gateway. The model itself decides whether to answer, clarify, read a source, use tools, create a project, delegate, schedule cron or use Kanban. Follow `charline-orchestration`; never replace model judgment with a Charline intent enum or scripted question sequence.

This skill does not implement a router, command dispatcher, Telegram handler, session store, scheduler, memory store or tool registry. It does not perform external writes, source reads or background work merely to display the menu.

## Verification Checklist

- [ ] Response is concise and in Russian
- [ ] Examples use ordinary user language rather than requiring slash commands
- [ ] `/commands` remains the route to the complete Hermes catalog
- [ ] No tools, external writes or duplicated Hermes infrastructure used
