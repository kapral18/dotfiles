---
sidebar_position: 5
---

# Session picker mechanics

This page holds the detailed behavior behind the [Session picker](session-picker.md) overview.

## Send command (`ctrl-s`)

`ctrl-s` turns the fzf query line into a command prompt:

1. Select one or more sessions, worktrees, or directories with `tab`.
2. Press `ctrl-s`.
3. Type the command.
4. `enter` dispatches to each selected entry's first idle shell pane.
5. `esc` cancels and returns to normal picker mode.

Mixed selections are supported:

- session rows dispatch directly.
- worktree rows resolve to a live session whose path matches or is a descendant of the selected path.
- directory rows resolve only by exact path match, so selecting `$HOME` cannot over-match an arbitrary session under home.
- when no match exists, a new session is spawned at the selected path before sending.

Spawned sessions use the same canonical name that a normal `enter` action would assign. Worktree rows derive `<repo_id>|<branch>` from cached metadata; directory rows use `session_name --$MODE` honoring `@pick_session_mode`.

The dispatch path snapshots fzf's `{+f}` selection during the `enter:transform` shell command. That matters because fzf deletes its temp selection file as soon as the transform shell exits. Snapshotting inside the transform avoids stale/deleted `{+f}` paths and keeps visual selection state aligned with what gets sent.

When the command creates sessions, `action_send_command.sh` posts a reload to fzf's listen socket so new sessions appear without a manual refresh.

## Options

### Popup geometry

| Option                       | Configured | Script default |
| ---------------------------- | ---------- | -------------- |
| `@pick_session_popup_height` | `70`       | `40`           |
| `@pick_session_popup_width`  | `80`       | `80`           |

### Scan and discovery

| Option                              | Default                                                       | Purpose                                     |
| ----------------------------------- | ------------------------------------------------------------- | ------------------------------------------- |
| `@pick_session_worktree_scan_roots` | `~/work`,`~/code`,`~/.backport/repositories`,`~/.local/share` | Roots scanned for git repos                 |
| `@pick_session_worktree_scan_depth` | `6`                                                           | Max `fd` depth for `.git` discovery         |
| `@pick_session_dir_exclude_file`    | `~/.config/tmux/pick_session_dir_exclude.txt`                 | `fd --exclude` patterns                     |
| `@pick_session_dir_include_hidden`  | `on`                                                          | Include hidden directories in home scan     |
| `@pick_session_github_login`        | unset                                                         | Override first-party remote owner detection |
| `@pick_session_mode`                | `directory`                                                   | Naming/discovery mode                       |

### Appearance

| Option                               | Default     | Purpose                                |
| ------------------------------------ | ----------- | -------------------------------------- |
| `@pick_session_fzf_prompt`           | unset       | Custom prompt                          |
| `@pick_session_fzf_ghost`            | unset       | Custom ghost text                      |
| `@pick_session_fzf_color`            | unset       | Custom fzf colors                      |
| `@pick_session_fzf_options`          | `--no-sort` | Extra fzf flags                        |
| `@pick_session_auto_rename_sessions` | `off`       | Auto-rename sessions to expected names |
| `@pick_session_filter_quick_1`       | `work`      | `alt-1` query, trailing slash appended |
| `@pick_session_filter_quick_2`       | `code`      | `alt-2` query, trailing slash appended |

## Ordering

The picker prioritizes active sessions above worktrees and directories. Rows are de-duplicated by path with priority `session > worktree > dir`.

The empty picker keeps `--no-sort`, preserving grouped/frecency order. For a non-empty query, matches remain in strict `session > worktree > dir` tiers and fzf relevance determines order within each tier. After the query is idle for 120 ms, a tiny Python daemon ranks the complete source rows with an off-screen fzf filter, stable-partitions them by kind, and reloads that order once. Interactive sorting stays disabled, so continuous typing neither forks a shell nor repeatedly reorders the visible list. Input reloads atomically refresh the source snapshot, and clearing the query restores it.

### Frecency

Session/worktree rows are ordered by a mix of recency and frequency so recently used work stays near the top without losing stable grouping.

### View filter (`alt-o`)

`alt-o` cycles:

1. all rows
2. dirty rows
3. review-needed rows
4. all rows

The GitHub picker uses `alt-r` for quote-reply; the session picker keeps `alt-r` for force refresh.

### Create worktree (`alt-c`)

`alt-c` enters a modal branch-name prompt. `enter` runs `,w add <branch>` at the selected repo root; `esc` cancels.

## Remove worktrees (`alt-x`)

`alt-x` removes selected worktree rows in the background and hides their rows optimistically while the cache refresh runs. When a root worktree selection maps to a wrapper directory such as `~/work/kibana`, the remover deletes only the worktrees reported by that repo's `git worktree list`. Ordinary non-worktree leftovers under an otherwise removable wrapper are preserved under `.bag/pickers/session/` before the empty wrapper is removed. If the wrapper also contains an independent git repo or worktree root, the wrapper is kept in place and those sibling git roots are neither deleted nor moved into `.bag`.

Deletion is boundary-guarded: the background remover only `rm`s targets that resolve to a strict descendant of `$HOME` or a configured `@pick_session_worktree_scan_roots` entry (the scan roots are passed through from the picker, which still holds tmux context). The roots themselves, `/`, empty paths, and anything resolving outside every approved root are refused.

Removing a plain (non-worktree) directory row also kills its tmux session. The picker resolves the exact session name while still attached and passes it to the background remover, so the session is torn down by name even though `$TMUX` is unset for the detached job.

## Hand off to GitHub (`alt-g`)

`alt-g` hands the selected row's PR/issue to the GitHub picker instead of switching sessions locally. It writes a `gh_picker_pin` seed and touches a `pick_session_switch_gh` sentinel inside the picker's owner-scoped handoff namespace, then aborts. The popup loop sees the sentinel, relaunches the GitHub picker, and that picker consumes `gh_picker_pin` at startup to seed the matching PR/issue on top (`pin_gh_first`). Slots are resolved through `handoff_namespace.py` in the explicit `TMUX_PICKER_HANDOFF_TOKEN` environment namespace inherited via `display-popup -e`, never through argv or top-level global mailbox files. The wrapper owner ends the namespace on normal exit; a picker launched without an inherited token begins, owns, and ends its own standalone namespace. See the GitHub picker's [Handoff bus](github-picker-mechanics.md#handoff-bus) for owner cleanup and the seven-day secure retained-context lifecycle used by Palantír handoffs.

## Refresh and caching

`ctrl-r` performs a synchronous quick session scan with last-known dirty badges, then backgrounds the full worktree/dir scan. `alt-r` forces a full refresh and blocks until quick + full scans complete.

After tmux-resurrect/continuum restores saved sessions, a post-restore hook waits for restore-time quick-only session hooks to settle, then runs a fast full worktree scan (`--skip-dirty --skip-gh`) followed by the normal enriched full scan in the background. That keeps session-only restore caches from hiding worktrees that do not currently have live tmux sessions.

Refresh preserves query and cursor position by reloading through the same ordered cache pipeline and using fzf tracking actions.

Session enumeration fails closed: if `tmux list-sessions` fails, index updates keep the last good cache and cache rehydration preserves existing rows rather than presenting worktrees/directories without sessions. Ordered snapshots also verify that their cache, mutation, pending, and frecency inputs did not change while ordering; a raced snapshot is discarded.

Main cache files live under `~/.cache/tmux/`:

| Cache                       | Purpose                                                  |
| --------------------------- | -------------------------------------------------------- |
| `pick_session_items.tsv`    | rendered rows                                            |
| `pick_session_gh.json`      | PR/issue metadata with smart TTLs                        |
| mutation/pending tombstones | optimistic hide for killed sessions or removed worktrees |

PR/issue cache TTLs are state-aware: open items refresh more often than merged/closed items, and cache misses have their own shorter TTL.

GitHub lookups are tri-state. A successful lookup writes fresh PR/issue metadata; a confirmed absence (the branch has no PR, or the issue does not resolve) clears any stale badge; a transient failure (rate limit, network error, timeout, `gh` unavailable) preserves the last-known cached badge instead of erasing it. Badges therefore survive a flaky `gh` call rather than flickering to empty.

## Worktree discovery

The indexer scans configured roots for git worktrees, checks dirty state in parallel, and enriches non-default branches with PR/issue metadata when `gh` is available.

Issue detection runs in this order:

1. `comma.w.issue.number` worktree-local git config.
2. Branch suffix heuristic such as `fix/1234-desc`.
3. PR `closingIssuesReferences` from the same `gh pr view` call.

Cross-repo closing issues preserve their exact `owner/repo` and do not rely on cwd inference.

## Session naming and collision recovery

Naming and path helpers are centralized in `pickers/session/lib/session_naming.sh`, shared by both regular open and send-command flows.

Name collisions first try the `@bag` recovery path: if the existing session points at a bagged removal path, it is renamed to `<name>@bag[N]`, freeing the canonical session name. Only non-bagged sessions at different paths fall back to `<name>@<basename>`.

## Popup performance

The first paint is cache-first. When the cache is unavailable, the picker falls back to live tmux sessions, zoxide recent dirs when available, and `$HOME`. Full indexing happens in the background so opening the popup remains snappy.
