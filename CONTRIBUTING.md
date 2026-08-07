# Contributing

## Change workflow

1. Read `AGENTS.md` and inspect Git status.
2. Define one bounded behavior and its acceptance evidence.
3. Add or change a focused test and observe RED.
4. Implement the smallest GREEN change.
5. Refactor without changing behavior.
6. Run focused tests, then the full suite.
7. Review diff and runtime evidence before claiming completion.

## Parallel workers

- One writer owns a file set at a time.
- Parallel workers use separate branches/worktrees after a clean commit.
- Worker briefs list exact files, side-effect boundary and completion evidence.
- Duplicate goals and overlapping file ownership are prohibited.
- Child summaries are claims until the parent verifies diffs, paths and test output.

## External actions

Reads and local drafts may run directly. Sending, Google Workspace writes, cron changes, deployment, publication, permissions and destructive actions require the latest exact preview and explicit confirmation, followed by read-back.
