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

Phase 6 requires fresh live proof; prior V1 evidence does not cover these flows:

1. Confirm Telegram's persistent menu button opens the native command list rather than a Web App, and `/charline` opens one native card with `Календарь`, `Почта`, `Файлы`, `Задачи`, `Проекты`, `Новая задача` and `Новый проект`; category details and `Назад` edit that card, while task/project buttons reuse their existing scoped centers.
2. Send a natural-language meeting request without duration; receive one short duration question, then no progress chatter and one complete preview; cancel without a write.
3. Repeat the request by Russian voice; verify the transcript and cancel at the final confirmation.
4. Request a busy slot; receive one conflict message with the nearest available start as an exact alternative preview.
5. Change one field after preview; verify the old confirmation is invalid and a new preview is required.
6. Separately confirm one sandbox Calendar creation; receive one concise result after exact read-back.
7. In the ordinary direct-message chat, start two independent bounded tasks in parallel; continue the conversation, inspect only current-chat work through `/agents` with no Gateway service jobs shown, and verify each completion is labelled and separately verified.
8. Opt into `/topic` separately; verify General remains one permanent main session, `/projects new [name]` and `Новый проект` explicitly create isolated topics, and two project conversations remain isolated from General and each other.
9. Ask one unrelated general question and verify Charline answers normally without forcing a menu or domain transaction.

## Release decision

- `repository-complete`: automated gates pass and docs match the installed interface.
- `profile-ready`: repository-complete plus active-profile gate.
- `production-verified`: profile-ready plus live read gates and confirmed sandbox effects.
