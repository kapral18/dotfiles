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

Spawned sessions use the same canonical name that a normal `enter` action would assign. Worktree rows derive `<repo_id>|<branch>` from cached metadata; directory rows use `session_name --$MODE` honoring `PICK_SESSION_MODE`.

The dispatch path snapshots fzf's `{+f}` selection during the `enter:transform` shell command. That matters because fzf deletes its temp selection file as soon as the transform shell exits. Snapshotting inside the transform avoids stale/deleted `{+f}` paths and keeps visual selection state aligned with what gets sent.

When the command creates sessions, `action_send_command.sh` posts a reload to fzf's listen socket so new sessions appear without a manual refresh.

## Options

Picker settings are `PICK_SESSION_*` environment variables (unset means the default below). The popup itself is sized by its `[[keys.command]]` entry in herdr's `config.toml` (90% × 90%).

### Scan and discovery

| Variable                           | Default                                        | Purpose                                     |
| ---------------------------------- | ---------------------------------------------- | ------------------------------------------- |
| `PICK_SESSION_WORKTREE_SCAN_ROOTS` | `~/code`,`~/.local/share`                      | Roots scanned for git repos                 |
| `PICK_SESSION_WORKTREE_SCAN_DEPTH` | `6`                                            | Max `fd` depth for `.git` discovery         |
| `PICK_SESSION_DIR_EXCLUDE_FILE`    | `~/.config/herdr/pick_session_dir_exclude.txt` | `fd --exclude` patterns                     |
| `PICK_SESSION_DIR_INCLUDE_HIDDEN`  | `on`                                           | Include hidden directories in home scan     |
| `PICK_SESSION_GITHUB_LOGIN`        | unset                                          | Override first-party remote owner detection |
| `PICK_SESSION_MODE`                | `directory`                                    | Naming/discovery mode                       |

### Appearance

| Variable                      | Default     | Purpose                                |
| ----------------------------- | ----------- | -------------------------------------- |
| `PICK_SESSION_FZF_PROMPT`     | unset       | Custom prompt                          |
| `PICK_SESSION_FZF_GHOST`      | unset       | Custom ghost text                      |
| `PICK_SESSION_FZF_COLOR`      | unset       | Custom fzf colors                      |
| `PICK_SESSION_FZF_OPTIONS`    | `--no-sort` | Extra fzf flags                        |
| `PICK_SESSION_FILTER_QUICK_1` | `code`      | `alt-1` query, trailing slash appended |
| `PICK_SESSION_FILTER_QUICK_2` | `share`     | `alt-2` query, trailing slash appended |

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

`alt-x` runs the remover synchronously from fzf so any confirmation for unsaved work or submodule safety opens inline in the existing picker context instead of trying to open another herdr popup. Safe selected worktree rows still remove in the background and hide optimistically only after the `,w remove --preflight` check says the selection is safe; choosing Force in the inline prompt continues the same removal with `--force`, while cancel leaves rows visible and unmutated. Detached-HEAD worktrees are included for `--paths` removals (the picker uses that path). When a root worktree selection maps to a wrapper directory such as `~/code/repo`, the remover deletes only the worktrees reported by that repo's `git worktree list`. Ordinary non-worktree leftovers under an otherwise removable wrapper are preserved under `.bag/pickers/session/` before the empty wrapper is removed. Existing timestamp archives survive a later removal that moves no leftovers. If the wrapper also contains an independent git repo or worktree root at any depth, the wrapper is kept in place and those sibling git roots are neither deleted nor moved into `.bag`. If the scan cannot read a directory, preservation stops before any content moves and cleans up its temporary scan status.

Preflight rejects missing paths, nested paths that are not checkout roots, failed Git queries, dirty files, and commits that would lose their retained refs. A linked or detached checkout can be removed when its commits remain reachable from another branch, tag, or remote-tracking ref. Removing an entire repository requires commits from every checkout HEAD (including detached siblings) and every local ref, including stashes, notes, branches, and tags to exist on remote-tracking refs, because its local refs disappear with the repository. Reflog-only and unreachable objects are outside this preflight check. The background remover repeats this check before deletion; Force explicitly bypasses the unsaved-work and submodule-history safeguards. Non-forced removal also refuses registered submodules and populated submodule administration stores, including deinitialized, removed, and per-worktree stores. The superproject’s remote refs do not retain its submodules’ independent objects. This guard requires Force even for clean, pushed submodules; it does not attempt to prove their nested history is recoverable.

Directory removal is boundary-guarded: targets must resolve to a strict descendant of `$HOME` or a configured `PICK_SESSION_WORKTREE_SCAN_ROOTS` entry. A target that is an approved root, contains one, resolves outside every approved root, or is `/` or empty is refused. This applies to recursive removal and empty-wrapper or bag cleanup, including Force. Removing a checkout directly under a scan root leaves the scan root in place. The picker forwards its exact scan-root setting to the background remover.

Plain (non-worktree) rows — directory rows, sessions outside a worktree, and stale worktree directories whose gitdir is gone — are deleted recursively, so `alt-x` always blocks them and only a second `alt-x` (Force) deletes them. Removing a plain directory row also closes its herdr workspace. The picker passes each selected row's exact workspace name to the background remover, so the workspace is closed by name.

## Hand off to GitHub (`alt-g`)

## Refresh and caching

`ctrl-r` performs a synchronous quick session scan with last-known dirty badges, then backgrounds the full worktree/dir scan. `alt-r` forces a full refresh and blocks until quick + full scans complete.

Quick/sessions-only publishes merge into the existing cache and refuse to replace a cache that already has worktree/dir rows with a discovery-empty snapshot. The `k18.pickers` plugin's `workspace.created` / `workspace.renamed` hooks use `--force --quick-only --defer-if-busy` so they still bypass TTL when the lock is free, but they leave an in-flight full scan (live refresh) alone instead of pre-empting it.

Refresh preserves query and cursor position by reloading through the same ordered cache pipeline and using fzf tracking actions.

A session's path is the directory its workspace was opened for, kept by `,w` and the picker in `~/.cache/herdr-pickers/workspace_paths.<server>.tsv`, one file per herdr server socket (herdr panes report a live cwd that follows `cd`). A row is keyed by workspace id and counts only while that workspace still has the recorded label. The `k18.pickers` plugin moves a row to the new label on `workspace.renamed`, drops it on `workspace.closed`, and drops rows of closed workspaces at startup, because herdr can reissue a closed workspace's id after a restart. A workspace without a matching row falls back to its first pane's cwd and is never matched by path alone; `,w remove` may still close it by its expected label when one of its panes is inside the worktree.

Session enumeration fails closed: if `herdr workspace list` fails, index updates keep the last good cache and cache rehydration preserves existing rows rather than presenting worktrees/directories without sessions. Ordered snapshots also verify that their cache, mutation, pending, and frecency inputs did not change while ordering; a raced snapshot is discarded.

Main cache files live under `~/.cache/herdr-pickers/`:

| Cache                       | Purpose                                                    |
| --------------------------- | ---------------------------------------------------------- |
| `pick_session_items.tsv`    | rendered rows                                              |
| `pick_session_gh.json`      | PR/issue metadata with smart TTLs                          |
| mutation/pending tombstones | optimistic hide for closed workspaces or removed worktrees |

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

Naming and path helpers are centralized in `pickers/session/lib/session_naming.sh`, shared by both regular open and send-command flows. Picker TSV rows preserve all six positional columns, including empty metadata and target fields, so a search-only match key cannot become a workspace name. Previews address that workspace by its exact label.

Session metadata places `expected=` last, after the status and GitHub fields. Its entire remaining value is the canonical workspace name, including the `|` in `<repo_id>|<branch>`; the picker treats that value as opaque. The picker never renames existing workspaces.

Directory and worktree rows share resolved-path collision handling. Regular open reuses a workspace already at the selected path; otherwise it allocates a unique suffix when another path holds the canonical name.

## Popup performance

The first paint is cache-first. When the cache is unavailable, the picker falls back to live herdr workspaces, zoxide recent dirs when available, and `$HOME`. Full indexing happens in the background so opening the popup remains snappy.
