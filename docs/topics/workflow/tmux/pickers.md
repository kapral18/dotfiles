---
sidebar_position: 1
---

# Tmux: pickers

This setup ships a URL picker, a session/worktree picker, and a GitHub picker (PRs/issues) designed to run inside tmux popups.

---

## URL picker

### Bindings

- `prefix` + `u` — open URL picker popup

### Options

| Option                    | Default                                                  | Description                                 |
| ------------------------- | -------------------------------------------------------- | ------------------------------------------- |
| `@pick_url_history_limit` | `screen`                                                 | How far back to scan for URLs               |
| `@pick_url_popup`         | configured `center,60%,35%` (fallback `center,100%,50%`) | Popup geometry                              |
| `@pick_url_fzf_flags`     | —                                                        | Extra flags passed to `fzf`                 |
| `@pick_url_open_cmd`      | —                                                        | Command used to open selected URL           |
| `@pick_url_extra_filter`  | —                                                        | Additional filter applied to URL candidates |

### Behavior

- De-duplicates path-prefix URLs: if both `https://site/x` and `https://site/x/y` are detected, it keeps the deeper path entry.
- Runs `fzf` with `FZF_DEFAULT_OPTS` cleared so global defaults don't distort the popup UI.
- Strips invisible Unicode formatting characters (zero-width space `U+200B`, ZWJ/ZWNJ, BOM, bidi marks, etc.) from captured pane content before URL extraction. These commonly leak in via copy-paste from web pages and would otherwise be appended to URLs (the bash extractor's `[^[:space:]]+` regex doesn't treat them as whitespace), causing 404s.

---

## Session picker

### Bindings

| Key            | Action                                                                                                                                                                                                                    |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `prefix` + `T` | Open session picker popup                                                                                                                                                                                                 |
| `enter`        | Open (switch to or create) the selected session                                                                                                                                                                           |
| `tab`          | Toggle multi-select on current row                                                                                                                                                                                        |
| `ctrl-x`       | Kill selected session(s) — optimistic hide                                                                                                                                                                                |
| `alt-x`        | Remove selected worktree(s) — optimistic hide                                                                                                                                                                             |
| `alt-y`        | Copy underlying path(s) to clipboard                                                                                                                                                                                      |
| `ctrl-s`       | **Send command** — enters a modal: type a command, `enter` sends it to selected entries (session/worktree/dir), `esc` cancels                                                                                             |
| `ctrl-r`       | Refresh: synchronous session scan with last-known dirty badges + background full rescan (worktrees/dirs + exact dirty badges). Query preserved; cursor stays at the same row index (see "How refresh preserves position") |
| `alt-r`        | Force full refresh (blocks until both quick + full scans complete, then reloads list). Same query/cursor preservation as `ctrl-r`                                                                                         |

> The GH picker rebinds `alt-r` to "quote-reply a comment" (it has no force-full-refresh equivalent — its `ctrl-r` is already fully synchronous with in-flight pre-emption). See the GH picker bindings table below.
> | `alt-p` | Open PR in browser (if the entry's branch has a linked PR) |
> | `alt-i` | Open issue in browser (if the entry's branch references an issue number) |
> | `alt-g` | Switch to GitHub picker (PRs/issues) |
> | `ctrl-/` | Toggle preview panel visibility |
> | `?` | Show keybinding help in the preview panel |
> | `shift-up/down` | Scroll preview (line) |
> | `shift-left/right` | Scroll preview (page) |

### Switching between pickers

`alt-g` switches between the session picker and the GitHub picker. The current popup closes and a new one opens with the correct dimensions (session picker uses configured `@pick_session_popup_*` sizes, GitHub picker uses 95%×95%). The loop logic lives in the outer wrapper scripts (`popup.sh` / `gh_popup.sh`), not in the inner picker scripts, because `tmux resize-popup` is not available.

### Entry types

The picker shows three kinds of entries, each with a Nerd Font icon and ANSI color:

| Icon        | Kind     | Description                          |
| ----------- | -------- | ------------------------------------ |
| `` (green)  | session  | Active tmux session                  |
| `` (orange) | worktree | Git worktree discovered on disk      |
| `` (blue)   | dir      | Directory from scan roots or `$HOME` |

Rows are de-duplicated by path: for the same path, only one entry is shown (priority: session > worktree > dir). If you select a directory and the picker creates or focuses a tmux session for it, that path reopens as a session row with the session icon while keeping the path-shaped label (for example `~/code/`) so path queries still match.

### Status badges

Badges appear inline after the entry name/path. They are computed at index time (zero cost at picker open).

| Badge                  | Meaning                                | How detected                                  |
| ---------------------- | -------------------------------------- | --------------------------------------------- |
| `∗` (dim yellow)       | Dirty — uncommitted tracked changes    | `git status --porcelain --untracked-files=no` |
| `⚠ stale` (dim yellow) | Stale worktree — gitdir target missing | `.git` file points to nonexistent gitdir      |
| `✗ gone` (dim red)     | Gone — path no longer exists on disk   | `os.path.isdir()` fails                       |

- Session entries inherit the status of their backing worktree.
- Dirty detection runs in parallel (half available cores) during the background index.
- Status flags are stored in the cache `meta` column (`status=dirty`, `status=stale`, etc.) and survive rehydration.

### GitHub PR/issue badges

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

### Preview pane

Visible by default on the right side. Content varies by entry type:

**Sessions:**

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

### Send command (`ctrl-s`)

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

### Options

**Popup geometry:**

| Option                       | Configured | Script default | Description      |
| ---------------------------- | ---------- | -------------- | ---------------- |
| `@pick_session_popup_height` | `70`       | `40`           | Popup height (%) |
| `@pick_session_popup_width`  | `80`       | `80`           | Popup width (%)  |

**Scan and discovery:**

| Option                              | Default                                                       | Description                                                                                                   |
| ----------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `@pick_session_worktree_scan_roots` | `~/work`,`~/code`,`~/.backport/repositories`,`~/.local/share` | <https://github.com/jayminwest/overstoryComma-separated> roots to scan for git repos                          |
| `@pick_session_worktree_scan_depth` | `6`                                                           | Max `fd` depth for `.git` discovery                                                                           |
| `@pick_session_dir_exclude_file`    | `~/.config/tmux/pick_session_dir_exclude.txt`                 | File with `fd --exclude` patterns (line-based, `#` comments, trailing `/` normalized, `.git` always excluded) |
| `@pick_session_dir_include_hidden`  | `on`                                                          | Include hidden directories in home scan                                                                       |
| `@pick_session_github_login`        | —                                                             | Override for first-party remote owner detection                                                               |
| `@pick_session_mode`                | `directory`                                                   | Picker mode                                                                                                   |

**Appearance:**

| Option                               | Default     | Description                                  |
| ------------------------------------ | ----------- | -------------------------------------------- |
| `@pick_session_fzf_prompt`           | —           | Custom fzf prompt string                     |
| `@pick_session_fzf_ghost`            | —           | Custom fzf ghost text                        |
| `@pick_session_fzf_color`            | —           | Custom fzf color scheme                      |
| `@pick_session_fzf_options`          | `--no-sort` | Extra fzf flags                              |
| `@pick_session_auto_rename_sessions` | `off`       | Auto-rename sessions to match expected names |

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

### How ordering works

Grouped/sorted ordering is produced by `pickers/session/filter.sh` (which delegates to `lib/filter_main.py` → `lib/pick_session_grouping.py:grouped_output`):

1. **Session-backed repo/worktree groups** first (sessions first within each group, then related worktrees)
2. **Worktree-only groups** next
3. **Directory entries** at the end (clustered by scan root and path)

Within and across groups the ordering keys are: `scan_root_rank` (position in `@pick_session_worktree_scan_roots`) → `scan_root_prefix` (top-level segment under the scan root) → `first_session_name` (alphabetical) → `group_path`. The current session sorts first within its group.

**One ordering, two read paths.** The grouped result is the _only_ user-facing order; cache storage is intentionally not the same shape as the display:

- Picker open prefers the precomputed snapshot (`pick_session_items_ordered.tsv`) for instant first paint.
- When the snapshot is stale or missing, `open_items.sh` falls back to `filter.sh --force-order`, which produces the same grouping live. This avoids the previous failure mode where stale-snapshot opens served raw cache order (with sessions injected at the top by `pick_session.sh` and worktrees clustered separately by `build_cache_refreshing_sessions_preserving_others`) and the next snapshot-backed open would reshuffle the list under the cursor.
- `filter.sh` has a `@pick_session_filter_passthrough_rows` (default `2000`) escape that drops back to raw cache when the list is large enough that grouping latency would be visible. **The passthrough is intentionally bypassed when `--force-order` is set** (both `filter.sh:72` and `filter_main.py:60` gate it on `force_order != 1`), so the `open_items.sh` stale-snapshot fallback always pays the grouping cost — that's the tradeoff for consistency. Tune the threshold lower to favor latency over consistency on user-typed filter calls (refresh, send-command reload, etc.), higher to favor consistency.

The picker uses fzf's native in-process filtering (no reload per keystroke) across the visible label and a hidden match key column.

- **Default behavior**: runs fzf with `--no-sort` (via `@pick_session_fzf_options`) so matches keep the picker's grouped ordering (sessions above worktrees above dirs).
- **Path intent**: when the query contains `/`, fzf sorting is ON so the narrowest matching path ranks highest (e.g. `work/` surfaces `~/work/` at the top). When it doesn't, sort is OFF. Scan-root directories and directory-backed session rows display with a trailing slash (e.g. `~/work/`) so `work/` matches them directly.
- **How it stays lag-free**: the sort state is synced by a tiny Python daemon that talks to fzf over its `--listen` Unix socket. It polls the live `query` + `sort` fields at 20 ms and `POST`s `toggle-sort` only on real transitions. fzf's `change` binding stays on the zero-cost `first` action, so typing and held backspace never fork a shell. Auto-toggle is correct for any edit (typing, paste, backspace, `ctrl-u`, `ctrl-w`, overwrite).
- **Manual override**: `alt-s` toggles fzf sort at any time. The daemon will re-sync on the next poll if the query disagrees with the override.

### How refresh preserves position (`ctrl-r` / `alt-r`)

Both refresh bindings issue `reload($filter_cmd ...)+track` against fzf's `--listen` socket. The `+track` chain is included for symmetry with other reload sites, **but in this picker it does not do identity-based cursor recovery** — that path in fzf's `UpdateList` (`terminal.go:1950`) is gated on `len(t.idNth) > 0` (`terminal.go:7799`), and the picker does not set `--id-nth`. fzf's other recovery path (index-based, `terminal.go:1972`) requires `t.revision.compatible(newRevision)`, but `actReload` calls `restart()` which `bumpMajor()`s the revision (`core.go:409`), making it incompatible. So neither recovery path fires for a reload chain in this picker; `+track` only sets `t.track` state.

What actually keeps the cursor in place across refresh is the **absence of any action that mutates `t.cy`**. The bindings intentionally do **not** chain `+clear-query`. `actClearQuery` mutates the input buffer, which fzf's main loop detects as `queryChanged` and fires the `change` event — and `change:first` (bound globally for snappy typing) calls `vset(0)`, jumping the cursor to row 0. The old `+track+clear-query` chain therefore landed the user at row 0 after every refresh, which read as the list "reshuffling". With `clear-query` removed, `queryChanged` stays false, no `change` event fires, and `t.cy` keeps its old value — the cursor stays at the **same row index** in the refreshed list (not necessarily the same item, since the refresh may have changed which item occupies that row). Use `ctrl-u` if you want to clear the query manually.

If true identity-based cursor recovery becomes a requirement, the fix is to set `--id-nth=<column-with-a-stable-key>` (e.g. the canonical session/target column) so `actReload` captures a `trackKey` and `UpdateList` can re-find the item after the major-revision bump.

### How caching works

- `pickers/session/index_update.sh` builds the cache (`~/.cache/tmux/pick_session_items.tsv`) and a precomputed ordered snapshot (`pick_session_items_ordered.tsv`) in the background.
- Dirty badges use a read-only tracked-change probe (`git --no-optional-locks ... status --porcelain --untracked-files=no`) with rename classification disabled. The picker only needs a clean/dirty boolean, so this avoids expensive index writes and rename detection without changing which tracked changes are considered dirty.
- `ctrl-r` keeps the synchronous path to session membership only and preserves cached dirty badges. The background full refresh recomputes exact dirty badges with one worker so it does not contend heavily with fzf/tmux; `alt-r` remains the blocking exact refresh path when you explicitly want to wait for that.
- Picker open prefers the ordered snapshot for instant first paint, validated against mutation/pending timestamps (bash `-nt` check, zero subprocess overhead).
- When the snapshot is stale, missing, or invalidated (after `ctrl-x` kill, `alt-x` remove, `enter`-time session injection, or a cache write from `index_update`), `open_items.sh` falls back to `filter.sh --force-order` so the live read uses the same grouped output as the snapshot path. A background `ordered_cache_update.sh` also fires so the next open hits the snapshot fast path again. Falling back to raw `items.sh` (cache order) is reserved for the case where `filter.sh` is missing.
- `items.sh` itself handles mutation tombstones internally on every read (`items_light_rehydrate.py` / `items_full_rehydrate.py`), so killed/removed entries never reappear regardless of which read path is taken.
- `tmux_opt` reads are cached: a single `tmux show-options -g` call replaces multiple sequential round-trips.
- Picker open does not auto-reload (prevents visible rerender/churn); use `ctrl-r` for a fresh rebuild.
- **Manual refresh pre-empts in-flight updates.** A `--force` invocation (which both `ctrl-r` and `alt-r` make via `filter.sh`) sends `SIGTERM` to any in-flight updater (typically a live-refresh tick), waits up to 3 s for it to release the cache lock, escalates to `SIGKILL` if needed, then runs cleanly. The pre-empted updater's cleanup uses an ownership-checked lock release so it can't unlink the successor's lock. Without this, a `ctrl-r` that landed during a live-refresh tick would silently no-op and the user would see stale rows after their explicit refresh.

### How worktree discovery works

- Filesystem-based: scans configured roots for `.git` directories/files using `fd`.
- A directory containing a `.git` directory is treated as a "root checkout"; a directory containing a `.git` file is treated as a sibling worktree.
- Avoids expensive `git worktree list` calls and prevents external tool worktrees outside scan roots from leaking in.
- Directory rows stop at discovered worktree roots: nested subdirectories under a worktree are not emitted as `dir` rows.
- Home directory discovery is capped to depth `6`; `@pick_session_dir_exclude_file` and `@pick_session_dir_include_hidden` constrain scope.

### Session naming

- Worktree-backed session names use a filesystem-derived identifier: the "repo" part is the home-relative wrapper/repo path (e.g., `work/kibana` or `.backport/repositories/elastic/kibana`) and the "branch" part is the wrapper-relative remainder path (for layouts created by `,w`).
- For singular checkouts (no linked worktrees), the branch token uses the repo default branch (origin/upstream HEAD, then common defaults, finally `main`) regardless of current checkout.
- For remote-prefix wrappers, `<remote>/<branch...>` becomes `<remote>__<branch...>` for third-party remotes; first-party owners (origin/upstream owner match or your login) keep plain `<branch...>`.
- Names are sanitized to tmux-safe identifiers (e.g., `1.8` becomes `1_8`; slashes like `feat/foo` are preserved).
- Sessions rooted in `.bag` locations (e.g. `~/.bag/worktree_remove/...`) are treated as stale and suppressed from the picker so they don’t mask newly recreated worktrees. If a worktree selection collides with an existing `.bag` session name, the picker renames the `.bag` session to `@bag` and recreates the canonical session at the real path.
- Worktree-backed session entries do not render `#{session_path}` in the visible label (filtering is focused on the session name). Directory-backed session entries keep the directory label so selecting a scan root such as `~/code/` does not remove that path-shaped entry from the picker.
- If multiple plain directory sessions point at the same path, the picker shows one row and prefers the canonical session target (for example `~/code/` targets `code`).
- The current session is marked `(current)` so it remains visible even after a rename.

### Popup performance

- Popup spawn temporarily overrides `default-shell` to `/bin/sh` during `display-popup` to avoid heavy-shell (fish, zsh with plugins) initialization overhead (~1 s). The original shell is restored atomically. `pickers/session/pick_session.sh` itself runs under `bash` via its shebang.
- The session picker and GitHub picker run `fzf` with `SHELL=bash` so preview / execute commands don't pay fish startup cost on every selection change.
- All pickers (URL, session, GitHub) run `fzf` with `FZF_DEFAULT_OPTS` cleared so global defaults don't distort the popup UI.
- For very large caches, `pickers/session/filter.sh` automatically falls back to passthrough mode (default threshold `2000` rows); tune with `@pick_session_filter_passthrough_rows`.
- For very large caches, first paint can defer `dir` rows (`@pick_session_defer_dir_rows_threshold`).
- On `alt-x` remove, selecting a root checkout/worktree hides all impacted rows immediately (sibling worktrees and matching sessions).
- `alt-x` removal will **not** tear down the active tmux session unless you explicitly selected it (prevents “remove sibling worktree” from killing the current session).
- When the cache is empty, the picker falls back to tmux sessions + `zoxide` recent dirs (if installed) + `~`.

---

## GitHub picker

A standalone fzf-based PR/issue picker. It reads PR and issue sections from its own YAML configs and displays them in `fzf` with rich preview, worktree markers, and review status badges. gh-dash is not a dependency.

### Bindings

| Key                | Action                                                                                                                                                                                           |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `prefix` + `G`     | Open GitHub picker popup (95%×95%)                                                                                                                                                               |
| `enter`            | Checkout worktree + focus (batch if items marked)                                                                                                                                                |
| `alt-b`            | Checkout + open Octo review (PRs only)                                                                                                                                                           |
| `ctrl-t`           | Batch worktree create (marked items)                                                                                                                                                             |
| `alt-o`            | Open in browser                                                                                                                                                                                  |
| `alt-y`            | Copy URL(s) to clipboard                                                                                                                                                                         |
| `tab`              | Mark/unmark item (multi-select)                                                                                                                                                                  |
| `alt-space`        | Mark/unmark item (alternate toggle)                                                                                                                                                              |
| `ctrl-s`           | Switch work/home mode                                                                                                                                                                            |
| `ctrl-r`           | Refresh from GitHub (current mode); query preserved, cursor stays at the same row index (see session picker's "How refresh preserves position" — same mechanism applies here, no `--id-nth` set) |
| `alt-g`            | Switch to session picker                                                                                                                                                                         |
| `alt-c`            | New comment (opens `$EDITOR`)                                                                                                                                                                    |
| `alt-r`            | Quote-reply a comment (not refresh — see note)                                                                                                                                                   |
| `alt-d`            | Edit your own comment                                                                                                                                                                            |
| `alt-e`            | Cycle preview: collapsed → body → all expanded                                                                                                                                                   |
| `ctrl-/`           | Toggle preview                                                                                                                                                                                   |
| `?`                | Show keybinding help                                                                                                                                                                             |
| `alt-j` / `alt-k`  | Page down / up                                                                                                                                                                                   |
| `shift-up/down`    | Scroll preview (line)                                                                                                                                                                            |
| `shift-left/right` | Scroll preview (page)                                                                                                                                                                            |

> `alt-r` is quote-reply here, not refresh. The GH picker's `ctrl-r` is fully synchronous and pre-empts any in-flight fetch (`gh_items.sh` kills the running fetch and starts a fresh one), so there is no separate "force full refresh" key. The session picker uses `alt-r` for force-full because its `ctrl-r` only blocks on the quick scan and backgrounds the full rescan.

### Entry source

Items come from the gh picker's standalone config files (`~/.config/tmux/scripts/pickers/github/gh-picker-work.yml` and `~/.config/tmux/scripts/pickers/github/gh-picker-home.yml`). Each file defines `prSections` and `issuesSections` with `title` and `filters` (GitHub Search syntax). The Python fetcher (`lib/gh_items_main.py`) parses these YAML files, runs GitHub Search API queries, and formats results as `fzf`-consumable TSV.

In work mode, the default config separates PRs that request **your** review (excluding those already in your team queue) from PRs that request **team** review, so the sections stay meaningfully distinct while global dedupe remains useful.

Within each section, items are sorted by GitHub creation time, newest first. The Pending Backports section sorts parent PRs the same way; sub-rows under each parent stay grouped by target branch.

#### Pending Backports section

A section can opt into custom logic by adding `source: backport-failures` (see `prSections[].source` in the work config). The fetcher runs the section's `filters` to seed a candidate list of merged PRs, then determines per-PR whether any backport target is still pending. A target branch is **pending** when it is requested by current labels **and** has no merged backport PR.

The pending check combines three signals so the section reflects reality even when the bot's comment trail is incomplete:

1. **`kibanamachine` comment tables** (`## 💔 All backports failed` / `## 💚 All backports created successfully`) — the historical record of bot attempts.
2. **Current `v<X>.<Y>.<Z>` labels** — branches whose label was removed are dropped (no longer needed). When the parent PR's `baseRefName` is `main`, the highest version label is treated as the main development version and excluded. If the PR has no version labels, this filter is skipped (preserves behavior on repos with different conventions).
3. **Title search for `[<branch>] … (#<parent>)` PRs** — manually-cherry-picked backports that the bot never commented about are still detected, with their actual `state` (`MERGED` / `OPEN` / `CLOSED`).

### Inline badges

| Badge        | Meaning                      | Color               |
| ------------ | ---------------------------- | ------------------- |
| `◆`          | Local worktree exists        | cyan (`38;5;81`)    |
| `󰄬`          | PR review — approved         | green (`38;5;42`)   |
| `󰀨`          | PR review — changes req.     | red (`38;5;196`)    |
| ``           | PR review — pending          | yellow (`38;5;220`) |
| `●` (green)  | CI — success                 | green (`38;5;42`)   |
| `●` (red)    | CI — failure                 | red (`38;5;196`)    |
| `●` (yellow) | CI — pending                 | yellow (`38;5;220`) |
| `⚡`         | Merge conflict (CONFLICTING) | orange (`38;5;209`) |

Review and CI badges are fetched via a chunked GraphQL phase that runs after the section searches and in parallel with the local worktree scan. PRs are split into small chunks (~5 per request) issued concurrently — GitHub's GraphQL evaluates aliases mostly serially within one request, so several small parallel queries finish far faster than one large batch.

The conflict badge is also sourced from GraphQL (`mergeable=CONFLICTING`). If GraphQL metadata is temporarily unavailable during a refresh, the picker keeps the last-known conflict badge until fresh metadata is fetched; in that case the badge is shown **dim** to indicate it may be stale (use `ctrl-r` to force revalidation).

Similarly, when GraphQL metadata is temporarily unavailable, the picker may show last-known **review** / **CI** badges in a **dim** style rather than dropping them abruptly.

### Worktree detection

The picker detects whether a PR or issue has a local worktree using a 3-tier heuristic:

1. `comma.w.issue.number` worktree-local git config (authoritative, set by `,w`)
2. Branch name suffix extraction (`-NNN` or `/NNN`)
3. Batched GraphQL `headRefName` matching against local worktree branches (catches PRs checked out by `,w prs`)

For issues, the picker also treats an issue as "local" when it is linked from an existing session/worktree entry in the session picker cache (e.g. via PR closing-issue references). This keeps issue indicators consistent across pickers.

### Actions

- **`enter` (no marks)**: single-item checkout. On a PR, runs `,gh-worktree pr <owner/repo> <number> --focus`; on an issue, runs `,gh-worktree issue <owner/repo> <number> --focus` (interactive branch prompt if the worktree doesn't exist yet). Exits the picker.
- **`enter` (items marked)**: batch worktree creation for all marked items (same as `ctrl-t`). PRs are created automatically; issues open `$EDITOR` with a batch naming buffer. Stays in the picker.
- **`ctrl-t`**: explicit batch worktree creation (same as `enter` with marks).
- **`alt-b` on a PR**: same as single `enter`, then opens Octo review in a new tmux window.
- **`alt-o`**: opens the PR/issue URL in the browser.
- **`alt-y`**: copies the URL(s) to the clipboard.
- **`alt-c`**: new comment — opens `$EDITOR`, posts on save.
- **`alt-r`**: quote-reply — pick a comment via fzf, quote it, open `$EDITOR`.
- **`alt-d`**: edit own comment — pick one of your comments via fzf, edit in `$EDITOR`.
- If the repo does not exist locally, `,gh-worktree` bootstraps it first via `,gh-tfork`.

### Cache

- TTL: 300 seconds (5 minutes).
- Cache file: `~/.cache/tmux/gh_picker_{work,home}.tsv`.
- `ctrl-r` forces a refresh bypassing the cache. Any in-flight background fetch is pre-empted via SIGTERM; the lock-holder's bash trap kills its python + `gh` subprocess descendants before releasing the lock so the new fetch starts with a clean GitHub search-rate-limit budget (otherwise orphaned `gh` calls would burn the budget and every section would error-fallback to prior cache, looking like "nothing changed").

### Preview pane

Shows PR/issue details: state, review decision, branches, author/assignee, changed files, labels, and body text. Uses `gh pr view` / `gh issue view` with `bat` for Markdown rendering. For PRs, it also shows `mergeable` (e.g. `MERGEABLE`, `CONFLICTING`) so the preview stays authoritative even if list badges are stale.

### Popup dimensions

The GitHub picker popup opens at 95%×95%. When switching to the session picker via `alt-g`, the popup closes and reopens at the session picker's configured dimensions. See [Switching between pickers](#switching-between-pickers) above.
