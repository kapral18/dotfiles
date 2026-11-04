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
4. `enter` dispatches to each selected entry's first detected shell pane, falling back to its first pane when no shell is found.
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

| Option                              | Default                                       | Purpose                                     |
| ----------------------------------- | --------------------------------------------- | ------------------------------------------- |
| `@pick_session_worktree_scan_roots` | `~/code`,`~/.local/share`                     | Roots scanned for git repos                 |
| `@pick_session_worktree_scan_depth` | `6`                                           | Max `fd` depth for `.git` discovery         |
| `@pick_session_dir_exclude_file`    | `~/.config/tmux/pick_session_dir_exclude.txt` | `fd --exclude` patterns                     |
| `@pick_session_dir_include_hidden`  | `on`                                          | Include hidden directories in home scan     |
| `@pick_session_github_login`        | unset                                         | Override first-party remote owner detection |
| `@pick_session_mode`                | `directory`                                   | Naming/discovery mode                       |

### Appearance

| Option                               | Default     | Purpose                                |
| ------------------------------------ | ----------- | -------------------------------------- |
| `@pick_session_fzf_prompt`           | unset       | Custom prompt                          |
| `@pick_session_fzf_ghost`            | unset       | Custom ghost text                      |
| `@pick_session_fzf_color`            | unset       | Custom fzf colors                      |
| `@pick_session_fzf_options`          | `--no-sort` | Extra fzf flags                        |
| `@pick_session_auto_rename_sessions` | `off`       | Auto-rename sessions to expected names |
| `@pick_session_filter_quick_1`       | `code`      | `alt-1` query, trailing slash appended |
| `@pick_session_filter_quick_2`       | `share`     | `alt-2` query, trailing slash appended |

## Ordering

The picker prioritizes active sessions above worktrees and directories. Rows are de-duplicated by path with priority `session > worktree > dir`.

The empty picker keeps `--no-sort`, preserving grouped/frecency order. For a non-empty query, matches remain in strict `session > worktree > dir` tiers and fzf relevance determines order within each tier. After the query is idle for 120 ms, a tiny Python daemon ranks the complete source rows with an off-screen fzf filter, stable-partitions them by kind, and reloads that order once. Interactive sorting stays disabled, so continuous typing neither forks a shell nor repeatedly reorders the visible list. Input reloads atomically refresh the source snapshot, and clearing the query restores it.

### Frecency

Session/worktree rows are ordered by a mix of recency and frequency so recently used work stays near the top without losing stable grouping. Concurrent accesses serialize updates to the frecency store.

### View filter (`alt-o`)

`alt-o` cycles:

1. all rows
2. dirty rows
3. review-needed rows
4. all rows

The GitHub picker uses `alt-r` for quote-reply; the session picker keeps `alt-r` for force refresh.

### Create worktree (`alt-c`)

`alt-c` enters a modal branch-name prompt. `enter` runs `,w add <branch>` at the selected repo root; `esc` cancels. Like send mode (`ctrl-s`), it does not open while an `alt-x` check is running or a force prompt is pending; press `esc` first.

## Remove worktrees (`alt-x`)

`alt-x` runs the remover synchronously from fzf so any confirmation for unsaved work or submodule safety opens inline in the existing picker context instead of trying to nest another tmux popup. Safe selected worktree rows still remove in the background and hide optimistically only after the `,w remove --preflight` check says the selection is safe; choosing Force in the inline prompt continues the same removal with `--force`, while cancel leaves rows visible and unmutated. Detached-HEAD worktrees are included for `--paths` removals (the picker uses that path). When a root worktree selection maps to a wrapper directory such as `~/code/repo`, the remover deletes only the worktrees reported by that repo's `git worktree list`. Ordinary non-worktree leftovers under an otherwise removable wrapper are preserved under `.bag/pickers/session/` before the empty wrapper is removed. Existing timestamp archives survive a later removal that moves no leftovers. If the wrapper also contains an independent git repo or worktree root at any depth, the wrapper is kept in place and those sibling git roots are neither deleted nor moved into `.bag`. If the scan cannot read a directory, preservation stops before any content moves and cleans up its temporary scan status.

Preflight rejects missing paths, nested paths that are not checkout roots, failed Git queries, dirty files, and commits that would lose their retained refs. A linked or detached checkout can be removed when its commits remain reachable from another branch, tag, or remote-tracking ref. Removing an entire repository requires commits from every checkout HEAD (including detached siblings) and every local ref, including stashes, notes, branches, and tags to exist on remote-tracking refs, because its local refs disappear with the repository. Reflog-only and unreachable objects are outside this preflight check. The background remover repeats this check before deletion; Force explicitly bypasses the unsaved-work and submodule-history safeguards. Non-forced removal also refuses registered submodules and populated submodule administration stores, including deinitialized, removed, and per-worktree stores. The superproject’s remote refs do not retain its submodules’ independent objects. This guard requires Force even for clean, pushed submodules; it does not attempt to prove their nested history is recoverable.

Directory removal is boundary-guarded: targets must resolve to a strict descendant of `$HOME` or a configured `@pick_session_worktree_scan_roots` entry. A target that is an approved root, contains one, resolves outside every approved root, or is `/` or empty is refused. This applies to recursive removal and empty-wrapper or bag cleanup, including Force. Removing a checkout directly under a scan root leaves the scan root in place. The picker forwards its exact scan-root setting to the background remover.

Plain (non-worktree) rows — directory rows, sessions outside a worktree, and stale worktree directories whose gitdir is gone — are deleted recursively, so `alt-x` always blocks them and only a second `alt-x` (Force) deletes them. Removing a plain directory row also kills its tmux session. The picker resolves the exact session name while still attached and passes it to the background remover, so the session is torn down by name even though `$TMUX` is unset for the detached job.

## Hand off to GitHub (`alt-g`)

## Refresh and caching

`ctrl-r` performs a synchronous quick session scan with last-known dirty badges, then backgrounds the full worktree/dir scan. `alt-r` forces a full refresh and blocks until quick + full scans complete.

After tmux-resurrect/continuum restores saved sessions, a post-restore hook waits for restore-time quick-only session hooks to settle, then runs a fast full worktree scan (`--skip-dirty --skip-gh`) followed by the normal enriched full scan in the background. That keeps session-only restore caches from hiding worktrees that do not currently have live tmux sessions.

Quick/sessions-only publishes merge into the existing cache and refuse to replace a cache that already has worktree/dir rows with a discovery-empty snapshot. Session create/rename hooks use `--force --quick-only --defer-if-busy` so they still bypass TTL when the lock is free, but they leave an in-flight full scan (post-restore or live refresh) alone instead of pre-empting it.

Refresh preserves query and cursor position by reloading through the same ordered cache pipeline and using fzf tracking actions.

Sessions with an empty tmux `session_path` use the active pane’s `pane_current_path` for indexing and worktree matching. Session existence is tracked by name even when neither path is available, so selecting its worktree does not try to create a duplicate session.

Session enumeration fails closed: if `tmux list-sessions` fails, index updates keep the last good cache and cache rehydration preserves existing rows rather than presenting worktrees/directories without sessions. Ordered snapshots also verify that their cache, mutation, pending, and frecency inputs did not change while ordering; a raced snapshot is discarded.

Main cache files live under `~/.cache/tmux/`:

| Cache                       | Purpose                                                  |
| --------------------------- | -------------------------------------------------------- |
| `pick_session_items.tsv`    | rendered rows                                            |
| `pick_session_gh.json`      | PR/issue metadata with smart TTLs                        |
| mutation/pending tombstones | optimistic hide for killed sessions or removed worktrees |

Session-cache injection uses the same directory lock as index publication and deletion. If a publisher is busy, opening a session leaves that snapshot intact and still switches immediately; the scheduled quick refresh can then add the session. Updaters preserve a live injector’s lock. Updater, injector, and action-pruner ownership transitions serialize under `pick_session_items.tsv.owner.flock`. Records include PID, start identity, command digest, and generation. Manual refresh preempts only a verified updater; injectors and pruners are nonpreemptible. Live PID-only or unverified owners remain busy, even when their command mentions the updater. The updater rechecks identity before TERM/KILL and releases only its own generation. It forgets completed generator PIDs and checks current parent/identity before child cleanup. These inspections do not provide atomic OS process handles. The five-second owner grace lets cleanup stop both generator children before escalation.

Pending removals, mutation tombstones, and their pruning use one advisory `.flock` file per resource, so publication cannot overwrite a concurrent append. Lock files persist after release; only the acquired file descriptor owns a lock.

PR/issue cache TTLs are state-aware: open items refresh more often than merged/closed items, and cache misses have their own shorter TTL.

Concurrent quick and full scans merge changed GitHub metadata under its own advisory lock after their lookups finish. Newer per-worktree results survive an older scan finishing later; unchanged entries cannot undo a full scan’s pruning.

GitHub lookups are tri-state. A successful lookup writes fresh PR/issue metadata; a confirmed absence (the branch has no PR, or the issue does not resolve) clears stale metadata; a transient failure (rate limit, network error, timeout) preserves the disk entry. Scans reuse its badges and links only when the cached branch and repository identity match the current worktree. This also applies to `--skip-gh`, which ignores TTL while retaining the identity check. A changed branch or repository suppresses old metadata in newly generated rows without deleting its disk entry; stale metadata for the same identity remains visible after a failed lookup.

Repository identity follows local remote resolution. Matching empty repository values retain the existing cache behavior; missing identity fields are ineligible for reuse. These checks apply when scans generate rows. The picker’s first paint still replays the cached TSV snapshot until refresh.

GitHub metadata resolves after live sessions join the index, so a contributor PR session receives the same dark-pink review treatment as its worktree row even when the quick session pass found it first. Rows whose linked upstream PR is `MERGED` or `CLOSED` are dimmed.

## Worktree discovery

The indexer scans configured roots for git worktrees, checks dirty state in parallel, and enriches non-default branches with PR/issue metadata when `gh` is available.

Issue detection runs in this order:

1. `comma.w.issue.number` worktree-local git config.
2. Branch suffix heuristic such as `fix/description-1234`.
3. PR `closingIssuesReferences` from the same `gh pr view` call.

Cross-repo closing issues preserve their exact `owner/repo` and do not rely on cwd inference.

## Session naming and collision recovery

Naming and path helpers are centralized in `pickers/session/lib/session_naming.sh`, shared by both regular open and send-command flows. Picker TSV rows preserve all six positional columns, including empty metadata and target fields, so a search-only match key cannot become a tmux session name. Previews address that session by its exact name; a stale target cannot fall back to a longer name with the same prefix.

Session metadata places `expected=` last, after the status and GitHub fields. Its entire remaining value is the canonical session name, including the `|` in `<repo_id>|<branch>`; the picker treats that value as opaque when renaming and switching sessions. Cached values that would change during sanitization are ignored, preserving the original selection. Renaming existing sessions requires `@pick_session_auto_rename_sessions` to be `on`; its default `off` preserves existing names. A failed rename keeps the original session selected.

Directory and worktree rows share resolved-path collision handling. Regular open reuses a session already at the selected path; otherwise it allocates a unique suffix when another path holds the canonical name. With auto-renaming enabled, it can rename the selected-path session to an available canonical name. Both regular open and send-command flows can also move a holder at a bagged removal path to `<name>@bag[N]`, freeing the canonical name, only when auto-renaming is enabled.

## Popup performance

The first paint is cache-first. When the cache is unavailable, the picker falls back to live tmux sessions, zoxide recent dirs when available, and `$HOME`. Full indexing happens in the background so opening the popup remains snappy.
