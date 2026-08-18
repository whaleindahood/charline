# V1 acceptance

Repository completion and production verification are separate. The first is automated; the second touches the active Hermes profile or external services and therefore requires its own exact confirmation.

## Automated gates

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\run_evals.py
.\.venv\Scripts\python.exe scripts\usage_report.py --days 7
```

Required results:

- full suite and all product evals pass;
- architecture tests find no second runtime or service SDK in `src/charline`;
- every external-write eval requires the latest exact preview, explicit confirmation and read-back;
- unknown write outcomes cannot be blindly retried;
- usage output contains aggregate counters only, never message content.
- architecture checks find no Charline session router, project database, scheduler or second Gateway;
- the Charline plugin registers the five daily views, `/charline`, `/projects` and its model tool without overriding upstream `/topic`;
- the Hermes patch contains only generic, capability-gated extension points required by the plugin.

## Active-profile gate

After reviewing the exact skill list and backup target, confirm one sync. Then require:

```powershell
.\.venv\Scripts\python.exe scripts\health_check.py
```

Expected: `status=consistent`, no mismatched or extra managed skills. Preserve the emitted backup manifest for rollback.

## Live read gates

These are read-only at the service level, but Google OAuth may refresh a local token:

```powershell
.\.venv\Scripts\python.exe scripts\runtime_check.py --hermes-home <path> --live-google
```

Required: supported Hermes version, valid Telegram config, clean doctor, exactly one running Gateway PID and successful authenticated Google read. Separately receive and answer one Telegram message in the primary chat.

An expired/revoked Google token is a failed gate. Re-authenticate through the installed Google Workspace setup helper and repeat the live read; credential-file presence alone is not evidence of working access.

## Confirmed sandbox effects

Each item gets its own concrete preview and confirmation; use non-production targets:

1. Create one Calendar event, narrowly list it by returned ID, then separately confirm deletion.
2. Send one email to a controlled address and read it back by returned message ID/search.
3. Append a marker to a sandbox Doc and update a sandbox Sheet cell; read back exact values.
4. Create one one-time Hermes reminder, list/read its schedule and prompt hash, observe one delivery, then separately confirm removal.

Do not use Drive share/delete as a V1 proof until the installed interface exposes sufficient permission/trash read-back.

## Conversational UX gates

The persistent Telegram command picker must show exactly `/today`, `/projects`, `/tasks`, `/schedules` and `/settings`. The complete technical Hermes catalog remains manually available through `/commands`.

Phase 6 requires fresh live proof; prior V1 evidence does not cover these flows:

1. Confirm the picker has exactly five daily entries. Main `/charline` must show a compact status card; project `/charline` must show exact-topic status. Neither Home card contains Calendar, Mail, Files, Research, Memory, New Task, New Project or all-Hermes launchers.
2. Send a natural-language meeting request without duration; receive one short duration question, then no progress chatter and one complete preview; cancel without a write.
3. Repeat the request by Russian voice; verify the transcript and cancel at the final confirmation.
4. Request a busy slot; receive one conflict message with the nearest available start as an exact alternative preview.
5. Change one field after preview; verify the old confirmation is invalid and a new preview is required.
6. Separately confirm one sandbox Calendar creation; receive one concise result after exact read-back.
7. In the ordinary direct-message chat, start two independent bounded tasks in parallel; continue the conversation, inspect only current-chat work through `/tasks` with no Gateway service jobs shown, and verify each completion is labelled and separately verified. `/agents` remains a manually reachable upstream diagnostic.
8. In root DM Main, send ordinary text, create A with `/projects new A`, use A, return to Main, create/use B and return to Main. Verify three stable, isolated Hermes sessions and no last-project redirect.
9. Verify `Новый проект` and the natural-language project tool use the same service and require an exact explicit creation step.
10. Restart the Gateway; verify native project metadata survives and stale/deleted topic state never redirects Main or another project.
11. From Main and A, create separate background work and test reminders; verify every completion returns to its exact origin.
12. Ask one unrelated general question in Main and verify Charline answers normally without forcing a menu or domain transaction.
13. Render Projects, Tasks, Schedules and Settings, restart Gateway, then use their read-only buttons; each card must reconstruct and edit in place. A pre-restart mutation confirmation must expire safely.
14. Verify stop-all, cron deletion and memory deletion require owner/chat/thread-bound confirmation and read-back.

## Release decision

- `repository-complete`: automated gates pass and docs match the installed interface.
- `profile-ready`: repository-complete plus active-profile gate.
- `production-verified`: profile-ready plus live read gates and confirmed sandbox effects.
