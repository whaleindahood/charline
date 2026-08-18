# Hermes Agent patch

This patch carries generic Hermes extension improvements needed by the standalone Charline plugin:

- capability-gated `ctx.platform_actions.ensure_private_topic`, delegating creation and persistence to the existing Telegram adapter;
- owner/thread scoping for the existing generic Telegram choice picker.
- capability-gated restart-safe plugin cards over the existing post-ACL `gateway_platform_event` hook;
- Telegram command-menu allowlists and explicit no-argument rewrites, including alias materialization;
- scoped interruption of one native async delegation.

`windows-calendar.patch` is the second, ordered patch. It keeps plain Python
tool calls off Git Bash on native Windows and kills the complete MSYS probe
tree on timeout. This prevents Google Workspace reads and writes from waiting
for the terminal tool's outer timeout when Git for Windows cannot spawn a child.

All Charline commands, project policy and project views live in `plugins/charline`; the patch contains no Charline router, command, state store or scheduler. It targets upstream commit `2c8a2b65aa148ceb178d2251c54a523af12092c9` (2026-08-17). The prior 300-KB product fork is obsolete.

Apply only to the exact commit recorded in `BASE_COMMIT`:

```powershell
git rev-parse HEAD
git apply --check C:\path\to\charline\patches\hermes-agent\charline.patch
git apply C:\path\to\charline\patches\hermes-agent\charline.patch
git apply --check C:\path\to\charline\patches\hermes-agent\windows-calendar.patch
git apply C:\path\to\charline\patches\hermes-agent\windows-calendar.patch
```

Verify an already-patched checkout with:

```powershell
git apply --reverse --check C:\path\to\charline\patches\hermes-agent\charline.patch
git apply --reverse --check C:\path\to\charline\patches\hermes-agent\windows-calendar.patch
```

After a Hermes upgrade, never force this patch. Rebase it on the new version, run the focused and full Hermes suites, then regenerate it.
