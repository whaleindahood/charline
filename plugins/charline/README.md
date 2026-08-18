# Charline Hermes plugin

This standalone plugin adds contextual `/charline`, `/today`, `/projects`, `/schedules`, `/settings`, the Telegram Task Center and `charline_projects` through Hermes extension points. It does not own polling, routing, sessions, memory, cron or workers.

Install from this repository's subdirectory at an immutable commit, enable `charline`, and explicitly grant `gateway.platform_actions`. Telegram Threaded Mode must be enabled and `platforms.telegram.extra.ignore_root_dm` must remain false.

Project creation is two-step: `/projects new <name>` returns an exact preview and one-use confirmation command; only `/projects confirm <digest>` calls Hermes' native topic action. The confirmation is consumed before the write. An unknown outcome is never retried automatically and requires manual Telegram/`dm_topics` reconciliation.

`/projects` reads `platforms.telegram.extra.dm_topics`; it owns no project database and does not write to project transcripts.

Read-only cards use the generic Hermes platform-event/card seam: callback chat, owner and thread are re-authorized, then the plugin rebuilds the view from native state and Telegram edits the same message. Only sensitive confirmations use bounded expiring RAM tokens. `/commands` remains manual and is intentionally outside the daily picker.

Rename/archive/delete are not exposed in V1. Telegram topic lifecycle and Hermes session-history lifecycle are separate, and the current rename primitive does not atomically update configured topic metadata. Keep history and reconcile explicitly rather than guessing or deleting it.
