# Release evidence

Store only sanitized release evidence here: commit ID, command, timestamp, exit status, test counts, skill names/hashes, runtime version, boolean checks and opaque resource IDs when needed.

Never store credentials, tokens, environment values, Telegram user/chat IDs, email bodies, calendar descriptions, document text, logs containing prompts, or database copies.

Suggested filenames:

- `YYYYMMDD-automated.json`
- `YYYYMMDD-profile.json`
- `YYYYMMDD-live-read.json`
- `YYYYMMDD-sandbox-effects.json`

An absent evidence file means the gate is unverified, not implicitly passed.

