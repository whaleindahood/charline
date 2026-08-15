# Operations

## Install

1. Back up the active Hermes profile through the supported Hermes backup command.
2. Run the repository tests.
3. Run `python scripts/sync_skills.py --dry-run` with explicit Hermes home and backup directory; review its exact create/replace list, obtain confirmation, then rerun without `--dry-run`.
4. Do not run two sync processes against the same profile.

On Windows, back up the existing Gateway launcher, stop the Gateway, then copy
`scripts/Hermes_Gateway.vbs` to
`%LOCALAPPDATA%\hermes\gateway-service\Hermes_Gateway.vbs`. It resolves the
base interpreter from `.venv\pyvenv.cfg` and retries only immediate startup
failures; the Startup shortcut remains the single owner.

Hermes integration changes are stored in `patches/hermes-agent/charline.patch`, pinned to `BASE_COMMIT`. A fresh install must pass `git apply --check` before applying it. An already-patched checkout must pass `git apply --reverse --check`. After upgrading Hermes, rebase and retest the patch; never force-apply it to a different base commit.

Skill sync is exception-safe: a caught activation failure restores the prior managed skill set. It is not crash-atomic; process or machine termination during activation can require rollback from the backup.

## Verify

1. Run `python scripts/health_check.py` and require `consistent` repo/profile state.
2. Run the preflight below.
3. Verify one read-only Google API request.
4. Verify the active Telegram route by receiving and answering a message.
5. Treat these as separate checks: repository consistency does not prove live runtime health.

If Google reports `invalid_grant` or a revoked token, use the installed Google Workspace setup helper to print a new authorization URL. The user completes consent, then supplies the one-time code directly to the helper. Never place that code in Git, logs, evidence files or chat transcripts. Repeat `--check-live` afterwards.

## Rollback

1. Stop the single Hermes Gateway before changing active skill files.
2. Restore the complete `productivity/charline` and `productivity/charline-*` set with `python scripts/restore_skills.py <backup-dir> --hermes-home <path>` after confirming the exact target.
3. Run the repository tests and health check.
4. Start one Gateway and verify Telegram plus a read-only Google request.

## Daily runtime

- Telegram uses the existing Hermes Gateway and active `default` profile.
- For quiet Russian Telegram UX, set `display.language: ru`; set `display.platforms.telegram.tool_progress`, `interim_assistant_messages` and `busy_ack_detail` to `off`/`false`. Keep `long_running_notifications` enabled when one editable heartbeat is useful for long/background work; disable it only for strictly final-only delivery.
- Keep `platforms.telegram.extra.rich_messages: true` for native Rich Message tables. The current pilot also uses `rich_drafts: true`; if a client leaves stale draft frames, set it to `false` and restart the Gateway. `/tasks` uses an editable native control card independently of rich drafts.
- Keep topic mode opt-in. After `/topic`, use one Telegram topic per independent project; `/projects` becomes the compact project overview and the root direct message becomes the lobby. Do not use Kanban unless shared durable worker state is required.
- Do not start a second process with the same Telegram bot token.
- Use Hermes Desktop/Dashboard for session, cron, skill and process inspection.

## Preflight

1. `hermes --version`
2. `hermes config check`
3. `hermes doctor`
4. Verify the active Telegram route by receiving a message in the main chat.
5. Run `python scripts/runtime_check.py --hermes-home <path> --live-google`; note that OAuth validation may refresh the local token.
6. Run the repository tests.

## Incident response

1. Identify the failing layer before restarting anything.
2. Check actual process/port state and recent logs.
3. On Windows launch failure, close the failed instance and retry once with a fresh process; then switch transport.
4. Do not weaken VPN, firewall or credential controls to make a prototype work.
5. Never report an external operation as complete without a verified handle/read-back.

## Legacy pilot

`C:\Users\Legion\Desktop\tgassistant` is frozen as `pilot-v1`. Do not delete or deploy it. Its FastAPI Mini App, Worker and tunnel are not part of Charline V1.
