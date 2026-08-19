# Charline Hermes plugin

This standalone plugin adds `/charline`, `/today`, `/projects`, personal `/tasks`, `/settings`, `charline_projects` and a narrow exact-event Calendar Fast Path through Hermes extension points. It does not own polling, routing, sessions, memory, cron, Kanban or workers.

The Charline UI is private-chat only. Personal tasks are exact `Задача: ` entries in native Hermes Memory; they are not delegations or processes. Raw Memory, cron, provider and process controls stay outside the daily UI. Calendar confirmations use existing durable plugin state and are bound to owner/chat/thread.

Install from this repository's subdirectory at an immutable commit, enable `charline`, and explicitly grant `gateway.platform_actions`. Telegram Threaded Mode must be enabled and `platforms.telegram.extra.ignore_root_dm` must remain false.

`/projects new <name>` explicitly creates/reuses an empty native topic. For a substantial natural-language request, the model calls `charline_projects(start)` with the complete request; Charline composes generic `ensure_private_topic` and `dispatch_agent_turn` actions. Hermes remains unaware of project-product semantics and owns the resulting topic session.

`/projects` reads `platforms.telegram.extra.dm_topics`; it owns no project database and does not write to project transcripts.

Read-only cards use the generic Hermes platform-event/card seam: callback chat, owner and thread are re-authorized, then the plugin rebuilds the view from native state and Telegram edits the same message. Only sensitive confirmations use bounded expiring RAM tokens. `/commands` remains manual and is intentionally outside the daily picker.

Rename/archive/delete are not exposed in V1. Telegram topic lifecycle and Hermes session-history lifecycle are separate, and the current rename primitive does not atomically update configured topic metadata. Keep history and reconcile explicitly rather than guessing or deleting it.
