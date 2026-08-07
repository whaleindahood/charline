# Release and capability matrix

## Supported V1 surface

| Capability | Read | Confirmed write | Verification |
|---|---|---|---|
| Calendar | list/agenda | create, delete | narrow list plus returned event ID |
| Gmail | search/get/labels | send, reply, modify | returned ID and narrow get/search |
| Drive | search/get/download | upload, create folder | narrow search/get |
| Docs | get | create, append | get and compare content marker |
| Sheets | get | create, update, append | get exact range/value |
| Research | browser/web evidence | none by default | source URL and retrieval time |
| Briefing | normalized multi-source snapshot | none | deterministic output/tests |
| Reminders | Hermes cron list/read | create/change/disable/delete | job read-back and prompt hash |
| Developer | inspect/test/review | repo edits | focused plus full tests |

## Explicit limitations

- Calendar has no get-by-ID, update or free/busy command in the installed Google skill. Update stays draft-only.
- Gmail has no draft or attachment command. “Draft” means local text until a supported draft API exists.
- Drive permission listing and trashed-state verification are unavailable. Share/delete remains draft-only.
- Docs supports plain create/append, not rich structural editing.
- The repository does not wrap Google APIs; the installed `google-workspace` CLI remains the interface and Google remains source of truth.
- No Mini App, tunnel, reverse proxy, second scheduler, router, memory or session store exists in V1.

## Release sequence

1. Clean review and full automated gates.
2. Exact preview and confirmation for active skill sync; keep backup manifest.
3. Profile health and read-only runtime checks.
4. Individually confirmed sandbox effects.
5. Record sanitized evidence under `docs/evidence/`; never record secrets or message/document bodies.
6. Tag only the commit whose evidence passed.

