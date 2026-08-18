# Main + native projects migration

Repository implementation and live-profile activation are separate operations. Do not delete old sessions or mutate the active profile during repository review.

## Preconditions

- Back up the complete Hermes profile, especially `config.yaml` and `state.db`.
- Record the running Hermes commit/profile and confirm exactly one Gateway owns Telegram polling.
- Confirm Telegram Private Chat Topics (Threaded Mode) are enabled for the bot DM.
- Review and install the pinned Charline plugin and the small Hermes compatibility patch.

## Approved migration

1. Stop the Gateway cleanly after explicit operator approval.
2. Back up the profile again and verify the backup can be read.
3. Disable Charline's reliance on upstream `/topic` mode using Hermes' supported `/topic off` or configuration path. Do not delete historical sessions or binding rows.
4. Set `platforms.telegram.extra.ignore_root_dm: false` (or remove the key) so root DM is processed normally.
5. Keep existing valid `platforms.telegram.extra.dm_topics` entries. Reconcile only confirmed Charline project topics; never guess a missing `thread_id` or redirect it to another project.
6. Install and enable `plugins/charline`, then explicitly grant `gateway.platform_actions` to that plugin.
7. Configure the five-entry owner menu and the `tasks: charline_tasks` rewrite shown in `OPERATIONS.md`; do not delete the underlying Hermes commands.
8. Start exactly one Gateway and run repository health checks.
9. In Main, send ordinary text and Russian voice; verify both keep the root session key before and after creating project A.
10. Create A with `/projects new A`, send messages in A, return to Main, create B, and verify Main/A/B use three distinct native Hermes session keys with no context bleed.
11. From Main and A, start bounded background work and a test reminder; verify each completion returns to its exact origin.
12. Open Projects/Schedules/Settings, restart Gateway and press read-only buttons on the old cards. They must reconstruct; old mutation confirmations must expire.
13. Restart the Gateway; verify `/projects` still lists native metadata and Main/A/B routing is unchanged.

## Rollback

Stop the Gateway, restore the backed-up profile/config and the previously pinned Hermes build/plugin set, then start one Gateway. Do not delete newly created Telegram topics or Hermes sessions automatically; archive or reconcile them only after review. If any source without `thread_id` routes into a project, stop immediately and restore the backup.
