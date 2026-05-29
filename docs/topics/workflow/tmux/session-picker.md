---
sidebar_position: 2
---

# Tmux: session picker

A fzf-based session/worktree/directory picker that runs inside a tmux popup. It indexes tmux sessions, git worktrees, and directories, badges them with git/GitHub status, and lets you switch, create, kill, or send commands to them.

Open it with `prefix` + `T`. Press `alt-g` to switch to the [GitHub picker](github-picker.md).

## Bindings

| Key                | Action                                                                                                                                                                                                                    |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `prefix` + `T`     | Open session picker popup                                                                                                                                                                                                 |
| `enter`            | Open (switch to or create) the selected session                                                                                                                                                                           |
| `tab`              | Toggle multi-select on current row                                                                                                                                                                                        |
| `ctrl-x`           | Kill selected session(s) — optimistic hide                                                                                                                                                                                |
| `alt-x`            | Remove selected worktree(s) — optimistic hide                                                                                                                                                                             |
| `alt-y`            | Copy underlying path(s) to clipboard                                                                                                                                                                                      |
| `alt-Y`            | Copy canonical session name(s) to clipboard (column 5)                                                                                                                                                                    |
| `alt-1` / `alt-2`  | Quick filter to the first/second scan root via its trailing-slash label (defaults `work/` / `code/`; override with `@pick_session_filter_quick_1` / `@pick_session_filter_quick_2`)                                       |
| `alt-o`            | Cycle the view filter: all → dirty only → review-needed only → all                                                                                                                                                        |
| `alt-c`            | **Create worktree** off the selected repo — enters a modal: type a branch name, `enter` runs `,w add <branch>` at the repo root, `esc` cancels                                                                            |
| `ctrl-s`           | **Send command** — enters a modal: type a command, `enter` sends it to selected entries (session/worktree/dir), `esc` cancels                                                                                             |
| `ctrl-r`           | Refresh: synchronous session scan with last-known dirty badges + background full rescan (worktrees/dirs + exact dirty badges). Query preserved; cursor stays at the same row index (see "How refresh preserves position") |
| `alt-r`            | Force full refresh (blocks until both quick + full scans complete, then reloads list). Same query/cursor preservation as `ctrl-r`                                                                                         |
| `alt-p`            | Open PR in browser (if the entry's branch has a linked PR)                                                                                                                                                                |
| `alt-i`            | Open issue in browser (if the entry's branch references an issue number)                                                                                                                                                  |
| `alt-g`            | Switch to GitHub picker (PRs/issues)                                                                                                                                                                                      |
| `ctrl-/`           | Toggle preview panel visibility                                                                                                                                                                                           |
| `?`                | Show keybinding help in the preview panel                                                                                                                                                                                 |
| `shift-up/down`    | Scroll preview (line)                                                                                                                                                                                                     |
| `shift-left/right` | Scroll preview (page)                                                                                                                                                                                                     |

> The GH picker rebinds `alt-r` to "quote-reply a comment" (it has no force-full-refresh equivalent — its `ctrl-r` is already fully synchronous with in-flight pre-emption). See the [GitHub picker bindings](github-picker.md#bindings).

## Switching between pickers

`alt-g` switches between the session picker and the GitHub picker. The current popup closes and a new one opens with the correct dimensions (session picker uses configured `@pick_session_popup_*` sizes, GitHub picker uses 95%×95%). The loop logic lives in the outer wrapper scripts (`popup.sh` / `gh_popup.sh`), not in the inner picker scripts, because `tmux resize-popup` is not available.

## Entry types

The picker shows three kinds of entries, each with a Nerd Font icon and ANSI color:

| Icon        | Kind     | Description                          |
| ----------- | -------- | ------------------------------------ |
| `` (green)  | session  | Active tmux session                  |
| `` (orange) | worktree | Git worktree discovered on disk      |
| `` (blue)   | dir      | Directory from scan roots or `$HOME` |

Rows are de-duplicated by path: for the same path, only one entry is shown (priority: session > worktree > dir). If you select a directory and the picker creates or focuses a tmux session for it, that path reopens as a session row with the session icon while keeping the path-shaped label (for example `~/code/`) so path queries still match.

## Status badges

Badges appear inline after the entry name/path. They are computed at index time (zero cost at picker open).

| Badge                  | Meaning                                | How detected                                  |
| ---------------------- | -------------------------------------- | --------------------------------------------- |
| `∗` (dim yellow)       | Dirty — uncommitted tracked changes    | `git status --porcelain --untracked-files=no` |
| `⚠ stale` (dim yellow) | Stale worktree — gitdir target missing | `.git` file points to nonexistent gitdir      |
| `✗ gone` (dim red)     | Gone — path no longer exists on disk   | `os.path.isdir()` fails                       |

- Session entries inherit the status of their backing worktree.
- Dirty detection runs in parallel (half available cores) during the background index.
- Status flags are stored in the cache `meta` column (`status=dirty`, `status=stale`, etc.) and survive rehydration.

## GitHub PR/issue badges

For non-default branches, the indexer queries `gh` to detect linked pull requests and issues. Badges appear inline after status badges.

| Badge        | Meaning                    | Icon (Nerd Font)                   | Color               |
| ------------ | -------------------------- | ---------------------------------- | ------------------- |
| `` (green)   | PR — open                  | `oct-git_pull_request` F407        | green (`38;5;42`)   |
| `` (purple)  | PR — merged                | `oct-git_pull_request` F407        | purple (`38;5;141`) |
| `` (red)     | PR — closed                | `oct-git_pull_request_closed` F4DC | red (`38;5;196`)    |
| `` (green)   | Issue — open               | `oct-issue_opened` F41B            | green (`38;5;42`)   |
| `` (purple)  | Issue — closed             | `oct-issue_closed` F41D            | purple (`38;5;141`) |
| `󰄬` (green)  | Review — approved          | `nf-md-check_circle` U+F012C       | green (`38;5;42`)   |
| `󰀨` (red)    | Review — changes requested | `nf-md-alert_circle` U+F0028       | red (`38;5;196`)    |
| `` (yellow)  | Review — pending           | `nf-oct-dot_fill` U+F444           | yellow (`38;5;220`) |
| `●` (green)  | CI — success               | Unicode bullet U+25CF              | green (`38;5;42`)   |
| `●` (red)    | CI — failure               | Unicode bullet U+25CF              | red (`38;5;196`)    |
| `●` (yellow) | CI — pending               | Unicode bullet U+25CF              | yellow (`38;5;220`) |

- **PR detection**: `gh pr view --json number,state,url,reviewDecision,closingIssuesReferences` with `cwd` set to the worktree path (infers repo and branch from git context).
- **Issue detection** (resolved in order, first match wins):
  1. `comma.w.issue.number` worktree-local git config (set by `,w`)
  2. Branch name suffix heuristic (`-NNN` or `/NNN`, e.g. `fix/1234-desc` → issue `1234`)
  3. PR `closingIssuesReferences` — issues linked via `Closes #N`, `Fixes #N`, etc. in the PR description (extracted from the same `gh pr view` call, zero extra network cost). The exact `owner/repo` from the reference is used as the `-R` override for `gh issue view`, so cross-repo closing issues and fork workflows resolve correctly without relying on `cwd` inference. Once a number is found, `gh issue view <num>` fetches the current state.
- Lookups run in parallel (half available cores) during the background index, adding no latency to picker open.
- Results are cached on disk (`~/.cache/tmux/pick_session_gh.json`) with smart TTLs: open items refresh every 10 min, merged/closed items every 24 h, cache misses every 1 h. Branch or remote changes invalidate immediately. Stale worktree paths are pruned on each write.
- PR/issue metadata is stored in the TSV cache `meta` column (`pr=NUMBER:STATE:REVIEW:CI:URL`, `issue=NUMBER:STATE:URL`). `REVIEW` is the PR review decision (`APPROVED`, `CHANGES_REQUESTED`, `REVIEW_REQUIRED`, or empty). `CI` is the CI status (`SUCCESS`, `FAILURE`, `PENDING`, or empty).
- The preview pane shows PR/issue details (number, state, review status, URL) at the top for session and worktree entries.
- `alt-p` opens the PR URL in the browser; `alt-i` opens the issue URL.

## Preview pane

Visible by default on the right side. Content varies by entry type:

**Sessions:**

- Activity `status` line classifying the active pane command: `agent (<cmd>)` for known coding agents (claude, cursor-agent, aider, codex, opencode, goose, amp, gemini, ralph, crush), `idle (shell)` for a login shell, `editing (<cmd>)` for editors, `busy (<cmd>)` otherwise
- Running command, session path, window count
- Last 20 non-blank lines of the active pane (`tmux capture-pane`)
- Empty panes show `(empty pane)`

**Worktrees / git directories:**

- Path, current branch, ahead/behind sync status
- `git status` changes (up to 8 lines)
- Recent commits (last 6)
- Stale worktrees show a diagnostic and fall back to `ls` contents

**Non-git directories:**

- `ls` contents (up to 20 entries)

## Send command (`ctrl-s`)

Enters a modal where the fzf query line becomes a command prompt:

1. Select one or more entries (sessions, worktrees, or directories) with `tab`
2. Press `ctrl-s` to enter send mode
3. Type the command to send
4. `enter` dispatches it to each selected entry's first idle shell pane (fish/zsh/bash/sh)
5. `esc` cancels and returns to normal mode

Batch semantics:

- Works with mixed selections of any kind: `session` rows dispatch directly; `worktree` rows resolve to a live session whose path matches (or is a descendant of) the selected path; `dir` rows resolve only by exact path match (the "descendant" rule applies to worktrees only — for dirs it would over-match, e.g. selecting `$HOME` would route to whichever session under your home directory was iterated first). When no match is found, a new session is spawned at the selected path before sending.
- Spawned sessions use the same canonical name pick_session.sh would assign on a regular `enter` (worktree: `<repo_id>|<branch>` derived from the cache's `meta` field; dir: `session_name --$MODE` honoring `@pick_session_mode`). The naming, sanitization, branch-fallback (`default_branch_for_root_checkout`), login-shell resolution, and `@bag` collision-recovery are all factored into `pickers/session/lib/session_naming.sh`, sourced by both pick_session.sh and action_send_command.sh — `bag_rename_if_needed` is the sole implementation, and pick_session.sh passes its in-memory cached session path to skip the lib's internal `tmux list-sessions` lookup on the hot `enter` path, then consumes the lib's `"OLD\tNEW"` stdout to keep its cache coherent with the rename.
- Name collisions on spawn first try the lib's `@bag` recovery flow (rename the existing session to `<name>@bag[N]` if it points at `~/.bag/worktree_remove/...` or `~/.bag/pickers/session/...`, then create the canonical session at the real path). Only when the holder is a non-bagged session at a different path does the code fall back to `<name>@<basename>`; pick_session.sh's path-keyed rename-on-enter will reconcile any divergent name on the next regular `enter` of that row.
- A short `sleep 0.3` is inserted after spawning so the shell finishes its readline/zle init before `send-keys` fires; without this, the first keystrokes can be eaten on fish/zsh with instrumented prompts.
- Each session is dispatched in an isolated subshell so a single transient failure (e.g. a session that disappeared between selection and dispatch) does not abort the batch — remaining sessions still receive the command.
- A `tmux display-message` summary is shown when any send fails, or when one or more selected paths could not be spawned.
- Set `PICK_SESSION_SEND_DEBUG_LOG=/path/to/log` in the picker's environment to get per-invocation parse/dispatch/spawn traces (the picker doesn't set this by default — useful for ad-hoc debugging).
- Dispatch goes through `pickers/lib/dispatch_async.sh`, which mints a per-binding mktemp snapshot of `{+f}` via `pickers/lib/snapshot_fzf_selection.sh` and then runs the consumer in the tmux background. Same primitive as `ctrl-x` and `alt-x`; there is no shared selection file to clobber across rapid keypresses.
- `dispatch_async.sh` is invoked from _inside_ the `enter:transform` shell command (not emitted in the printed action string). fzf substitutes `{+f}` into the transform body's shell command and removes that temp file as soon as the shell exits (see `executeCommand` in fzf `terminal.go` around line 5413/5507). If the dispatch were emitted inside the printed action, the `{+f}` token there would already be a literal path that fzf had just deleted, and the consumer would receive a dead path. Snapshotting _during_ the transform shell sidesteps that race.
- Snapshotting happens at `enter`-time, so toggling marks with `tab` while in send mode is honored.
- After spawning + sending, `action_send_command.sh` posts `reload($filter_cmd --refresh --force-order)+track` to fzf's `--listen` socket so newly-spawned sessions become visible without a manual `ctrl-r`. The reload uses the same quick session scan as `ctrl-r`, preserving cached dirty badges until the background full refresh recomputes them. Only fires when this run actually created sessions (sends to existing-only selections leave the cache unchanged, so the post would be churn). `dispatch_async.sh` inlines `FZF_SOCK`/`FZF_PORT`/`FZF_API_KEY` into the `tmux run-shell -b` command string because tmux's background runner uses the server's env rather than the caller's. The `+track` is included for symmetry with `ctrl-r`/`alt-r`, but in this picker it's effectively a no-op for cursor recovery (see "How refresh preserves position" below); cursor stability after the reload comes from the fact that no `change` event fires, so `change:first` never resets `t.cy`.

## Options

**Popup geometry:**

| Option                       | Configured | Script default | Description      |
| ---------------------------- | ---------- | -------------- | ---------------- |
| `@pick_session_popup_height` | `70`       | `40`           | Popup height (%) |
| `@pick_session_popup_width`  | `80`       | `80`           | Popup width (%)  |

**Scan and discovery:**

| Option                              | Default                                                       | Description                                                                                                   |
| ----------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `@pick_session_worktree_scan_roots` | `~/work`,`~/code`,`~/.backport/repositories`,`~/.local/share` | Comma-separated roots to scan for git repos                                                                   |
| `@pick_session_worktree_scan_depth` | `6`                                                           | Max `fd` depth for `.git` discovery                                                                           |
| `@pick_session_dir_exclude_file`    | `~/.config/tmux/pick_session_dir_exclude.txt`                 | File with `fd --exclude` patterns (line-based, `#` comments, trailing `/` normalized, `.git` always excluded) |
| `@pick_session_dir_include_hidden`  | `on`                                                          | Include hidden directories in home scan                                                                       |
| `@pick_session_github_login`        | —                                                             | Override for first-party remote owner detection                                                               |
| `@pick_session_mode`                | `directory`                                                   | Picker mode                                                                                                   |

**Appearance:**

| Option                               | Default     | Description                                        |
| ------------------------------------ | ----------- | -------------------------------------------------- |
| `@pick_session_fzf_prompt`           | —           | Custom fzf prompt string                           |
| `@pick_session_fzf_ghost`            | —           | Custom fzf ghost text                              |
| `@pick_session_fzf_color`            | —           | Custom fzf color scheme                            |
| `@pick_session_fzf_options`          | `--no-sort` | Extra fzf flags                                    |
| `@pick_session_auto_rename_sessions` | `off`       | Auto-rename sessions to match expected names       |
| `@pick_session_filter_quick_1`       | `work`      | `alt-1` quick-filter query (trailing `/` appended) |
| `@pick_session_filter_quick_2`       | `code`      | `alt-2` quick-filter query (trailing `/` appended) |

**Cache and performance:**

| Option                                         | Default        | Description                                                |
| ---------------------------------------------- | -------------- | ---------------------------------------------------------- |
| `@pick_session_cache_ttl`                      | `60`           | Cache freshness threshold (seconds)                        |
| `@pick_session_cache_wait_ms`                  | `0`            | Max wait for cache on cold start (ms)                      |
| `@pick_session_pre_refresh`                    | `off`          | Run cache update before fzf (off = snappy popup)           |
| `@pick_session_filter_passthrough_rows`        | `2000`         | Row count threshold to skip expensive regroup/sort         |
| `@pick_session_defer_dir_rows_threshold`       | `0` (disabled) | Row count threshold to defer `dir` rows on first paint     |
| `@pick_session_mutation_tombstone_ttl`         | `300`          | How long kill/remove tombstones suppress entries (seconds) |
| `@pick_session_session_tombstone_live_grace_s` | `2`            | Grace period for session tombstones vs live sessions       |

**Live refresh:**

| Option                                      | Default | Description                             |
| ------------------------------------------- | ------- | --------------------------------------- |
| `@pick_session_live_refresh_ttl`            | `20`    | Live refresh cycle TTL (seconds)        |
| `@pick_session_live_refresh_interval_ms`    | `1500`  | Interval between refresh ticks          |
| `@pick_session_live_refresh_start_delay_ms` | `5000`  | Delay before first live refresh         |
| `@pick_session_live_refresh_pause_on_multi` | `on`    | Pause live refresh during multi-select  |
| `@pick_session_live_refresh_pause_on_query` | `on`    | Pause live refresh while typing a query |

## How ordering works

Grouped/sorted ordering is produced by `pickers/session/filter.sh` (which delegates to `lib/filter_main.py` → `lib/pick_session_grouping.py:grouped_output`):

1. **Session-backed repo/worktree groups** first (sessions first within each group, then related worktrees)
2. **Worktree-only groups** next
3. **Directory entries** at the end (clustered by scan root and path)

Within and across groups the ordering keys are: `scan_root_rank` (position in `@pick_session_worktree_scan_roots`) → `scan_root_prefix` (top-level segment under the scan root) → `first_session_name` (alphabetical) → `group_path`. The current session sorts first within its group.

### Frecency ordering

The structural grouping above is the **baseline**: it's what you see on a fresh setup before any usage history exists. As soon as you start switching sessions, the picker layers a usage-based (frecency) re-sort on top:

- Every `client-session-changed` event logs the session's path to a small store (`~/.cache/tmux/pick_session_frecency.tsv`) via `pickers/session/lib/frecency.py`. The score is zoxide-style: a `rank` that accumulates on each access, decayed by the age of the last access (bucketed: <1h ×4, <1d ×2, <1w ×0.5, older ×0.25). Entries whose path no longer exists are pruned on each write.
- When the store is non-empty, `grouped_output` re-sorts the structural result by frecency **within kind tiers**: sessions stay above worktrees above dirs (the picker's core invariant), but within each tier the rows you use most/most-recently float to the top. Unscored rows keep their structural order (stable sort), so the list "evolves toward frecency as you use it" without caps and without ever dropping a session below a hotter worktree or dir.
- `frecency.py` is imported by both grouping callers (`filter_main.py` and `items_hide_selected_main.py`) so the `alt-x`/`ctrl-x` repaint orders identically to the open/refresh paths.
- A session switch changes ordering without touching the item cache, so the ordered snapshot would otherwise go stale silently. `open_items.sh` and `ordered_cache_update.sh` both treat the snapshot as stale when `pick_session_frecency.tsv` is newer than it, so the next open reflects updated usage and regenerates the snapshot in the background.

### View filter (`alt-o`)

`alt-o` cycles a transient view filter through **all → dirty only → review-needed only → all** (`pickers/session/action_only_cycle.sh` holds the per-picker cycle state and emits an fzf `reload`+`change-header` action). The reload runs `filter.sh --only=<mode>`, which filters rows by the cache `meta` column before grouping:

- `dirty` keeps rows whose `meta` has `status=…,dirty`.
- `review` keeps rows whose `meta` has a `pr=` segment with review decision `CHANGES_REQUESTED` or `REVIEW_REQUIRED`.

The `--only` filter is a python-only view transform; it bypasses the `@pick_session_filter_passthrough_rows` escape (like `--force-order`). It is transient: a `ctrl-x`/`alt-x` repaint goes through `items_hide_selected.sh` (which doesn't carry the only-mode) and returns to the unfiltered view.

### Create worktree (`alt-c`)

`alt-c` enters a modal where the query line becomes a `new branch:` prompt (same scaffolding as send-mode, separate flag so `enter` can tell the two apart). On `enter`, `pickers/session/action_create_worktree.sh` resolves the repo root behind the selected row (worktree/session `target`, else the enclosing `.git` via `worktree_root_dir_for_path`), then runs `,w add <branch>` with `cwd` at that root. `,w` creates the worktree **and** its tmux session; the action then reindexes (`--quick-only`) and posts a `reload` so the new entry appears without a manual `ctrl-r`. If the selected row isn't inside a git repo, or `,w` is not on `PATH`, a `tmux display-message` reports it and nothing is created.

**One ordering, two read paths.** The grouped result is the _only_ user-facing order; cache storage is intentionally not the same shape as the display:

- Picker open prefers the precomputed snapshot (`pick_session_items_ordered.tsv`) for instant first paint.
- When the snapshot is stale or missing, `open_items.sh` falls back to `filter.sh --force-order`, which produces the same grouping live. This avoids the previous failure mode where stale-snapshot opens served raw cache order (with sessions injected at the top by `pick_session.sh` and worktrees clustered separately by `build_cache_refreshing_sessions_preserving_others`) and the next snapshot-backed open would reshuffle the list under the cursor.
- `filter.sh` has a `@pick_session_filter_passthrough_rows` (default `2000`) escape that drops back to raw cache when the list is large enough that grouping latency would be visible. **The passthrough is intentionally bypassed when `--force-order` is set** (both `filter.sh:72` and `filter_main.py:60` gate it on `force_order != 1`), so the `open_items.sh` stale-snapshot fallback always pays the grouping cost — that's the tradeoff for consistency. Tune the threshold lower to favor latency over consistency on user-typed filter calls (refresh, send-command reload, etc.), higher to favor consistency.
- The `alt-x` remove and `ctrl-x` kill bindings repaint via `reload($hide_selected_cmd ...)` → `items_hide_selected.sh`, a _third_ caller of the shared grouping. It must order rows identically to the snapshot/`filter.sh` paths or the list visibly reshuffles right after a removal. To guarantee that, the dir-row sort key (scan-root dirs hoisted above their descendants within a rank) lives **only** in `grouped_output`'s default `dir_sort_key` in `pick_session_grouping.py` — the single source of truth shared by `filter_main.py` and `items_hide_selected_main.py`. Previously `filter_main.py` carried that hoist in a private `dir_sort_override` while `items_hide_selected_main.py` did not, so an `alt-x` repaint dropped the scan-root quick-access rows (`~`, `~/.backport/repositories`, `~/.local/share`) out of their pinned positions until the next `ctrl-r`/reopen.

The picker uses fzf's native in-process filtering (no reload per keystroke) across the visible label and a hidden match key column.

- **Default behavior**: runs fzf with `--no-sort` (via `@pick_session_fzf_options`) so matches keep the picker's grouped ordering (sessions above worktrees above dirs).
- **Path intent**: when the query contains `/`, fzf sorting is ON so the narrowest matching path ranks highest (e.g. `work/` surfaces `~/work/` at the top). When it doesn't, sort is OFF. Scan-root directories and directory-backed session rows display with a trailing slash (e.g. `~/work/`) so `work/` matches them directly.
- **How it stays lag-free**: the sort state is synced by a tiny Python daemon that talks to fzf over its `--listen` Unix socket. It polls the live `query` + `sort` fields at 20 ms and `POST`s `toggle-sort` only on real transitions. fzf's `change` binding stays on the zero-cost `first` action, so typing and held backspace never fork a shell. Auto-toggle is correct for any edit (typing, paste, backspace, `ctrl-u`, `ctrl-w`, overwrite).
- **Manual override**: `alt-s` toggles fzf sort at any time. The daemon will re-sync on the next poll if the query disagrees with the override.

## How refresh preserves position (`ctrl-r` / `alt-r`)

Both refresh bindings issue `reload($filter_cmd ...)+track` against fzf's `--listen` socket. The `+track` chain is included for symmetry with other reload sites, **but in this picker it does not do identity-based cursor recovery** — that path in fzf's `UpdateList` (`terminal.go:1950`) is gated on `len(t.idNth) > 0` (`terminal.go:7799`), and the picker does not set `--id-nth`. fzf's other recovery path (index-based, `terminal.go:1972`) requires `t.revision.compatible(newRevision)`, but `actReload` calls `restart()` which `bumpMajor()`s the revision (`core.go:409`), making it incompatible. So neither recovery path fires for a reload chain in this picker; `+track` only sets `t.track` state.

What actually keeps the cursor in place across refresh is the **absence of any action that mutates `t.cy`**. The bindings intentionally do **not** chain `+clear-query`. `actClearQuery` mutates the input buffer, which fzf's main loop detects as `queryChanged` and fires the `change` event — and `change:first` (bound globally for snappy typing) calls `vset(0)`, jumping the cursor to row 0. The old `+track+clear-query` chain therefore landed the user at row 0 after every refresh, which read as the list "reshuffling". With `clear-query` removed, `queryChanged` stays false, no `change` event fires, and `t.cy` keeps its old value — the cursor stays at the **same row index** in the refreshed list (not necessarily the same item, since the refresh may have changed which item occupies that row). Use `ctrl-u` if you want to clear the query manually.

If true identity-based cursor recovery becomes a requirement, the fix is to set `--id-nth=<column-with-a-stable-key>` (e.g. the canonical session/target column) so `actReload` captures a `trackKey` and `UpdateList` can re-find the item after the major-revision bump.

## How caching works

- `pickers/session/index_update.sh` builds the cache (`~/.cache/tmux/pick_session_items.tsv`) and a precomputed ordered snapshot (`pick_session_items_ordered.tsv`) in the background.
- Dirty badges use a read-only tracked-change probe (`git --no-optional-locks ... status --porcelain --untracked-files=no`) with rename classification disabled. The picker only needs a clean/dirty boolean, so this avoids expensive index writes and rename detection without changing which tracked changes are considered dirty.
- `ctrl-r` keeps the synchronous path to session membership only and preserves cached dirty badges. The background full refresh recomputes exact dirty badges with one worker so it does not contend heavily with fzf/tmux; `alt-r` remains the blocking exact refresh path when you explicitly want to wait for that.
- Picker open prefers the ordered snapshot for instant first paint, validated against mutation/pending timestamps (bash `-nt` check, zero subprocess overhead).
- When the snapshot is stale, missing, or invalidated (after `ctrl-x` kill, `alt-x` remove, `enter`-time session injection, or a cache write from `index_update`), `open_items.sh` falls back to `filter.sh --force-order` so the live read uses the same grouped output as the snapshot path. A background `ordered_cache_update.sh` also fires so the next open hits the snapshot fast path again. Falling back to raw `items.sh` (cache order) is reserved for the case where `filter.sh` is missing.
- `items.sh` itself handles mutation tombstones internally on every read (`items_light_rehydrate.py` / `items_full_rehydrate.py`), so killed/removed entries never reappear regardless of which read path is taken.
- `tmux_opt` reads are cached: a single `tmux show-options -g` call replaces multiple sequential round-trips.
- Picker open does not auto-reload (prevents visible rerender/churn); use `ctrl-r` for a fresh rebuild.
- **Manual refresh pre-empts in-flight updates.** A `--force` invocation (which both `ctrl-r` and `alt-r` make via `filter.sh`) sends `SIGTERM` to any in-flight updater (typically a live-refresh tick), waits up to 3 s for it to release the cache lock, escalates to `SIGKILL` if needed, then runs cleanly. The pre-empted updater's cleanup uses an ownership-checked lock release so it can't unlink the successor's lock. Without this, a `ctrl-r` that landed during a live-refresh tick would silently no-op and the user would see stale rows after their explicit refresh.

## How worktree discovery works

- Filesystem-based: scans configured roots for `.git` directories/files using `fd`.
- A directory containing a `.git` directory is treated as a "root checkout"; a directory containing a `.git` file is treated as a sibling worktree.
- Avoids expensive `git worktree list` calls and prevents external tool worktrees outside scan roots from leaking in.
- Directory rows stop at discovered worktree roots: nested subdirectories under a worktree are not emitted as `dir` rows.
- Home directory discovery is capped to depth `6`; `@pick_session_dir_exclude_file` and `@pick_session_dir_include_hidden` constrain scope.

## Session naming

- Worktree-backed session names use a filesystem-derived identifier: the "repo" part is the home-relative wrapper/repo path (e.g., `work/kibana` or `.backport/repositories/elastic/kibana`) and the "branch" part is the wrapper-relative remainder path (for layouts created by `,w`).
- For singular checkouts (no linked worktrees), the branch token uses the repo default branch (origin/upstream HEAD, then common defaults, finally `main`) regardless of current checkout.
- For remote-prefix wrappers, `<remote>/<branch...>` becomes `<remote>__<branch...>` for third-party remotes; first-party owners (origin/upstream owner match or your login) keep plain `<branch...>`.
- Names are sanitized to tmux-safe identifiers (e.g., `1.8` becomes `1_8`; slashes like `feat/foo` are preserved).
- Sessions rooted in `.bag` locations (e.g. `~/.bag/worktree_remove/...`) are treated as stale and suppressed from the picker so they don’t mask newly recreated worktrees. If a worktree selection collides with an existing `.bag` session name, the picker renames the `.bag` session to `@bag` and recreates the canonical session at the real path.
- Worktree-backed session entries do not render `#{session_path}` in the visible label (filtering is focused on the session name). Directory-backed session entries keep the directory label so selecting a scan root such as `~/code/` does not remove that path-shaped entry from the picker.
- If multiple plain directory sessions point at the same path, the picker shows one row and prefers the canonical session target (for example `~/code/` targets `code`).
- The current session is marked `(current)` so it remains visible even after a rename.

## Popup performance

- Popup spawn temporarily overrides `default-shell` to `/bin/sh` during `display-popup` to avoid heavy-shell (fish, zsh with plugins) initialization overhead (~1 s). The original shell is restored atomically. `pickers/session/pick_session.sh` itself runs under `bash` via its shebang.
- The session picker and GitHub picker run `fzf` with `SHELL=bash` so preview / execute commands don't pay fish startup cost on every selection change.
- All pickers (URL, session, GitHub) run `fzf` with `FZF_DEFAULT_OPTS` cleared so global defaults don't distort the popup UI.
- For very large caches, `pickers/session/filter.sh` automatically falls back to passthrough mode (default threshold `2000` rows); tune with `@pick_session_filter_passthrough_rows`.
- For very large caches, first paint can defer `dir` rows (`@pick_session_defer_dir_rows_threshold`).
- On `alt-x` remove, selecting a root checkout/worktree hides all impacted rows immediately (sibling worktrees and matching sessions).
- `alt-x` removal will **not** tear down the active tmux session unless you explicitly selected it (prevents “remove sibling worktree” from killing the current session).
- Stale worktrees (the `⚠ stale` badge — directory present but its `.git` file points at a missing `worktrees/<name>` admin dir) are orphans the indexer can't attribute to a root checkout, so it labels them `wt_root:` with `target == path`. `action_remove_worktrees.sh` detects the broken git linkage and routes them to `remove_plain_dir.sh` (safe `rm -rf` under `$HOME`) instead of `remove_all_worktrees.sh`, whose `rev-parse --is-inside-work-tree` guard would otherwise bail and leave the directory on disk while the row was optimistically hidden.
- **Stale guard also applies to `session` rows, not just `worktree` rows.** A tmux session backed by a stale worktree is placed by the indexer in its own single-member group whose `root_checkout` _is_ the orphan dir, so the session is tagged `sess_root:`. Without a guard this was dangerous: the router resolves a session's root via `worktree_root_dir_for_path`, which reads the `.git` file's `gitdir:` text and walks `…/main/.git/worktrees/<name>` up to the **live** root checkout (e.g. `kibana/main`) regardless of the broken linkage. Combined with `sess_root:` that set `is_root_selection=1` and dispatched `remove_all_worktrees.sh <live-root>`, which by design `rm -rf`s the entire repo wrapper (`~/work/<repo>`, including `main` and every sibling worktree). `alt-x` on a single stale `8.19` session could therefore wipe the whole `~/work/kibana` tree. The `session` branch now runs the same broken-linkage check as the `worktree` branch and routes the orphan dir to `remove_plain_dir.sh`, so only that one directory is removed.
- When the cache is empty, the picker falls back to tmux sessions + `zoxide` recent dirs (if installed) + `~`.

## Related

- [Pickers overview + URL picker](pickers.md)
- [GitHub picker](github-picker.md)
- [Worktrees](../git-identity/worktrees.md)
