---
sidebar_position: 3
title: Icons and scheduled jobs
---

# Icons and scheduled jobs

## Custom App Icons

- Mapping: [`home/app_icons/readonly_icon_mapping.yaml`](../../../home/app_icons/readonly_icon_mapping.yaml)
- Script: [`home/exact_bin/executable_,apply-app-icons.tmpl`](../../../home/exact_bin/executable_,apply-app-icons.tmpl)
- Hook: [`home/.chezmoiscripts/run_onchange_after_05-apply-app-icons.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_05-apply-app-icons.sh.tmpl)

Note: [`home/app_icons/`](../../../home/app_icons/) is ignored by `chezmoi` via [`home/.chezmoiignore`](../../../home/.chezmoiignore). The script reads icon assets from the repo source directory.

## Scheduled jobs (crontab)

A user crontab is installed (replacing the existing one) from a repo-managed file:

- Crontab contents: [`home/crontab`](../../../home/crontab)
- Hook: [`home/.chezmoiscripts/run_onchange_after_05-install-crontab.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_05-install-crontab.sh.tmpl)

Crontab behavior:

| Piece           | Detail                                                     |
| --------------- | ---------------------------------------------------------- |
| Install command | `crontab "$CHEZMOI_SOURCE_DIR/crontab"`                    |
| Trigger         | hash-gated; re-installs only when `home/crontab` changes   |
| Shipped jobs    | none; the file is empty, so installing it clears the table |

Edit [`home/crontab`](../../../home/crontab) and `chezmoi apply` to change the schedule, or run `crontab -l` to inspect the installed table. To opt out, remove the hook script and clear the table with `crontab -e`.
