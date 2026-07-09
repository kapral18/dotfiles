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

Path-like queries containing `/` toggle fzf sorting on so the narrowest matching path wins. Non-path queries keep `--no-sort`, preserving grouped picker order. A tiny Python daemon watches fzf's listen socket and toggles sort without forking a shell on every keystroke.

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

`alt-x` removes selected worktree rows in the background and hides their rows optimistically while the cache refreshes. When a root worktree selection maps to a wrapper directory such as `~/work/kibana`, the remover deletes only the worktrees reported by that repo's `git worktree list`. Ordinary non-worktree leftovers under an otherwise removable wrapper are preserved under `.bag/pickers/session/` before the empty wrapper is removed. If the wrapper also contains an independent git repo or worktree root, the wrapper is kept in place and those sibling git roots are neither deleted nor moved into `.bag`.

## Refresh and caching

`ctrl-r` performs a synchronous quick session scan with last-known dirty badges, then backgrounds the full worktree/dir scan. `alt-r` forces a full refresh and blocks until quick + full scans complete.

After tmux-resurrect/continuum restores saved sessions, a post-restore hook waits for restore-time quick-only session hooks to settle, then runs a fast full worktree scan (`--skip-dirty --skip-gh`) followed by the normal enriched full scan in the background. That keeps session-only restore caches from hiding worktrees that do not currently have live tmux sessions.

Refresh preserves query and cursor position by reloading through the same ordered cache pipeline and using fzf tracking actions.

Main cache files live under `~/.cache/tmux/`:

| Cache                       | Purpose                                                  |
| --------------------------- | -------------------------------------------------------- |
| `pick_session_items.tsv`    | rendered rows                                            |
| `pick_session_gh.json`      | PR/issue metadata with smart TTLs                        |
| mutation/pending tombstones | optimistic hide for killed sessions or removed worktrees |

PR/issue cache TTLs are state-aware: open items refresh more often than merged/closed items, and cache misses have their own shorter TTL.

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
