---
sidebar_position: 3
title: Operations and commands
---

# Operations and commands

## Refresh behavior

Opening `:PackDashboard` renders cached/known state immediately, then starts an async online refresh unless `vim.g.pack_dashboard_refresh_on_open = false`.

Every long-running mode shares one per-row experience:

- affected rows show an inline spinner immediately.
- the operation runs per plugin.
- each row resolves as soon as that plugin finishes.
- only two full renders bookend the run; intermediate updates are single-line changes.

This applies to:

| Key                | Mode                                                 |
| ------------------ | ---------------------------------------------------- |
| `R`                | Online refresh; fetches and re-evaluates each plugin |
| `r`                | Offline/local status; no network fetch               |
| `<CR>` / `u` / `U` | Update pending plugins                               |
| `V`                | Heal drift                                           |
| `C`                | Clean orphans                                        |

When a filter/search is active, refresh/update actions target only visible rows. Clear filters first to operate on every managed plugin.

## Dashboard tuning

| Global                                    | Default |
| ----------------------------------------- | ------- |
| `vim.g.pack_dashboard_width_ratio`        | `0.68`  |
| `vim.g.pack_dashboard_height_ratio`       | `0.68`  |
| `vim.g.pack_dashboard_min_width`          | `84`    |
| `vim.g.pack_dashboard_min_height`         | `18`    |
| `vim.g.pack_dashboard_margin`             | `6`     |
| `vim.g.pack_dashboard_fast_scroll`        | `true`  |
| `vim.g.pack_dashboard_ascii`              | `false` |
| `vim.g.pack_dashboard_refresh_on_open`    | `true`  |
| `vim.g.pack_dashboard_fetch_concurrency`  | `8`     |
| `vim.g.pack_dashboard_skip_risk_confirm`  | `false` |
| `vim.g.pack_dashboard_skip_clean_confirm` | `false` |

Repeated `:PackDashboard` calls reuse the existing floating window. Use `:PackDashboard!` to force-close and reopen without starting a refresh.

## Commands

| Command                       | Purpose                                            |
| ----------------------------- | -------------------------------------------------- |
| `:PackDashboard`              | Open the dashboard                                 |
| `:PackSync`                   | Raw online `vim.pack` report; fetch remotes first  |
| `:PackStatus`                 | Raw offline report                                 |
| `:PackDashboardStats`         | Print last check counters and timestamps           |
| `:PackTrace [plugin]`         | Show load state, trigger metadata, and load reason |
| `:PackLoad <plugin>`          | Force-load one plugin                              |
| `:PackLockInfo`               | Show lockfile path/count/mtime                     |
| `:PackLockExport <path>`      | Copy the lockfile to a path                        |
| `:PackLockImport <path>`      | Overwrite the lockfile from a path                 |
| `:PackPolicyRebuild [plugin]` | Recompute the tag/branch heuristic                 |

Dashboard/trace buffers are transient and excluded from session persistence to avoid polluting `auto-session` restores.
