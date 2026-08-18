# Charline product contract

Charline is the owner's personal ChatGPT plus Codex/Claude Code experience in Telegram, powered by one Hermes Agent runtime.

## Main

The root Telegram DM is a permanent, unrestricted conversation. The owner writes or speaks naturally. Hermes decides whether to answer, read a connected source, remember a personal task, create a cron job, use tools, or ask a necessary clarification. Charline does not implement an intent enum, question tree, JSON router, or model-independent workflow for interpreting requests.

The daily menu is a set of state views, not a capability launcher:

- `Сегодня` — calendar, personal tasks, reminders, plans and important project results;
- `Проекты` — durable project topics and their state;
- `Задачи` — the owner's personal tasks, not Hermes processes;
- `Расписания` — native Hermes cron jobs;
- `Настройки` — connected accounts, models/providers, memory, access, timezone and notifications.

## Projects

Work that needs a durable context or produces a substantial artifact belongs in a native Telegram topic. Ordinary questions and small direct operations stay in Main. Hermes makes that judgment from the request; Charline does not hard-code task categories.

A project topic behaves like a persistent Codex/Claude Code session:

- the model asks only clarifications it actually needs;
- it plans and revises the plan itself;
- it has the normal Hermes terminal, file, browser, memory, cron and delegation capabilities;
- it can continue unattended and use native Kanban when work, handoffs or review must survive a process restart;
- it reports verified results, artifacts, changed files, links and real blockers;
- later messages continue the same topic session.

A topic is a conversation/workstream, not a repository. Several topics may use the same directory, repository or deployed system. Workspace choice is therefore a model decision grounded in the request, topic history and available environment; Hermes asks when the target is genuinely ambiguous.

## Native Hermes boundary

- Hermes owns the model loop, Telegram polling, sessions, Memory, cron, delegation, Kanban and tool registry.
- `delegate_task` is for bounded fork/join work.
- Kanban is for durable multi-stage or multi-worker work that must survive restarts, retain handoffs or wait for the owner.
- Cron is used for reminders, briefings, scheduled project work and proactive checks. It may be created by the model when clearly implied by the owner's request or established plan.
- Results and blockers return to the exact originating Main/topic route.
- Charline adds product policy, native topic creation and deterministic state cards; it does not duplicate Hermes infrastructure.

## Access model

Charline is single-owner. Inside a chosen workspace Hermes operates with its configured full-access agent capabilities. The meaning of the request determines whether deployment, publication or another external effect belongs to the requested outcome; there is no Charline-side keyword router. Irreversible or economically consequential effects remain fail-closed when the request did not clearly authorize them.

## Completion

Success is not “the tool ran.” The topic must make it possible to understand:

- what was requested;
- what was done and verified;
- what changed;
- where the artifacts or deployment are;
- what failed or remains blocked;
- what the owner can ask next.

The topic remains until the owner removes it.
