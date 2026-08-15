# Hermes Agent patch

This patch carries Charline's tested Hermes integration without creating a second runtime.

Apply only to the exact commit recorded in `BASE_COMMIT`:

```powershell
git rev-parse HEAD
git apply --check C:\path\to\charline\patches\hermes-agent\charline.patch
git apply C:\path\to\charline\patches\hermes-agent\charline.patch
```

Verify an already-patched checkout with:

```powershell
git apply --reverse --check C:\path\to\charline\patches\hermes-agent\charline.patch
```

After a Hermes upgrade, never force this patch. Rebase it on the new version, run the focused and full Hermes suites, then regenerate it.
