# Operations

## Install

1. Back up the active Hermes profile through the supported Hermes backup command.
2. Run the repository tests.
3. Run `python scripts/sync_skills.py` with an explicit Hermes home and a new backup directory.
4. Do not run two sync processes against the same profile.

Skill sync is exception-safe: a caught activation failure restores the prior managed skill set. It is not crash-atomic; process or machine termination during activation can require rollback from the backup.

## Verify

1. Run `python scripts/health_check.py` and require `consistent` repo/profile state.
2. Run the preflight below.
3. Verify one read-only Google API request.
4. Verify the active Telegram route by receiving and answering a message.
5. Treat these as separate checks: repository consistency does not prove live runtime health.

## Rollback

1. Stop the single Hermes Gateway before changing active skill files.
2. Restore the complete `productivity/charline-*` set from one matching backup.
3. Run the repository tests and health check.
4. Start one Gateway and verify Telegram plus a read-only Google request.

## Daily runtime

- Telegram uses the existing Hermes Gateway and active `default` profile.
- Do not start a second process with the same Telegram bot token.
- Use Hermes Desktop/Dashboard for session, cron, skill and process inspection.

## Preflight

1. `hermes --version`
2. `hermes config check`
3. `hermes doctor`
4. Verify the active Telegram route by receiving a message in the main chat.
5. Verify Google Workspace authentication with its setup `--check` command.
6. Run the repository tests.

## Incident response

1. Identify the failing layer before restarting anything.
2. Check actual process/port state and recent logs.
3. On Windows launch failure, close the failed instance and retry once with a fresh process; then switch transport.
4. Do not weaken VPN, firewall or credential controls to make a prototype work.
5. Never report an external operation as complete without a verified handle/read-back.

## Known baseline risk

Hermes Doctor reported SQLite 3.45.1 as affected by the WAL-reset bug. Upgrade Hermes/runtime through the supported update path only after a backup and explicit approval; verify `hermes doctor` afterwards.

## Legacy pilot

`C:\Users\Legion\Desktop\tgassistant` is frozen as `pilot-v1`. Do not delete or deploy it. Its FastAPI Mini App, Worker and tunnel are not part of Charline V1.
