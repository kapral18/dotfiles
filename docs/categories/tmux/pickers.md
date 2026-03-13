# Tmux: pickers

Back: [`docs/categories/tmux/index.md`](index.md)

This setup ships a URL picker and a session/worktree picker designed to run
inside a tmux popup.

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

- De-duplicates path-prefix URLs: if both `https://site/x` and
  `https://site/x/y` are detected, it keeps the deeper path entry.
- Runs `fzf` with `FZF_DEFAULT_OPTS` cleared so global defaults don't distort
  the popup UI.

---

## Session picker

### Bindings

| Key                | Action                                                                                                    |
| ------------------ | --------------------------------------------------------------------------------------------------------- |
| `prefix` + `T`     | Open session picker popup                                                                                 |
| `enter`            | Open (switch to or create) the selected session                                                           |
| `tab`              | Toggle multi-select on current row                                                                        |
| `ctrl-x`           | Kill selected session(s) — optimistic hide                                                                |
| `alt-x`            | Remove selected worktree(s) — optimistic hide                                                             |
| `ctrl-s`           | **Send command** — enters a modal: type a command, `enter` sends it to selected session(s), `esc` cancels |
| `ctrl-r`           | Refresh list (grouped ordering + background cache rebuild)                                                |
| `alt-r`            | Force full refresh                                                                                        |
| `ctrl-/`           | Toggle preview panel visibility                                                                           |
| `?`                | Show keybinding help in the preview panel                                                                 |
| `shift-up/down`    | Scroll preview (line)                                                                                     |
| `shift-left/right` | Scroll preview (page)                                                                                     |

### Entry types

The picker shows three kinds of entries, each with a Nerd Font icon and ANSI
color:

| Icon        | Kind     | Description                          |
| ----------- | -------- | ------------------------------------ |
| `` (green)  | session  | Active tmux session                  |
| `` (orange) | worktree | Git worktree discovered on disk      |
| `` (blue)   | dir      | Directory from scan roots or `$HOME` |

Rows are de-duplicated by path: for the same path, only one entry is shown
(priority: session > worktree > dir).

### Status badges

Badges appear inline after the entry name/path. They are computed at index time
(zero cost at picker open).

| Badge                  | Meaning                                | How detected                                  |
| ---------------------- | -------------------------------------- | --------------------------------------------- |
| `∗` (dim yellow)       | Dirty — uncommitted tracked changes    | `git status --porcelain --untracked-files=no` |
| `⚠ stale` (dim yellow) | Stale worktree — gitdir target missing | `.git` file points to nonexistent gitdir      |
| `✗ gone` (dim red)     | Gone — path no longer exists on disk   | `os.path.isdir()` fails                       |

- Session entries inherit the status of their backing worktree.
- Dirty detection runs in parallel (8 threads) during the background index.
- Status flags are stored in the cache `meta` column (`status=dirty`,
  `status=stale`, etc.) and survive rehydration.

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

1. Select one or more sessions with `tab`
2. Press `ctrl-s` to enter send mode
3. Type the command to send
4. `enter` dispatches it to each selected session's first idle shell pane
   (fish/zsh/bash/sh)
5. `esc` cancels and returns to normal mode

### Options

**Popup geometry:**

| Option                       | Configured | Script default | Description      |
| ---------------------------- | ---------- | -------------- | ---------------- |
| `@pick_session_popup_height` | `70`       | `40`           | Popup height (%) |
| `@pick_session_popup_width`  | `80`       | `80`           | Popup width (%)  |

**Scan and discovery:**

| Option                              | Default                                                       | Description                                                                                                   |
| ----------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `@pick_session_worktree_scan_roots` | `~/work`,`~/code`,`~/.backport/repositories`,`~/.local/share` | https://github.com/jayminwest/overstoryComma-separated roots to scan for git repos                            |
| `@pick_session_worktree_scan_depth` | `6`                                                           | Max `fd` depth for `.git` discovery                                                                           |
| `@pick_session_dir_exclude_file`    | `~/.config/tmux/pick_session_dir_exclude.txt`                 | File with `fd --exclude` patterns (line-based, `#` comments, trailing `/` normalized, `.git` always excluded) |
| `@pick_session_dir_include_hidden`  | `on`                                                          | Include hidden directories in home scan                                                                       |
| `@pick_session_github_login`        | —                                                             | Override for first-party remote owner detection                                                               |
| `@pick_session_mode`                | `directory`                                                   | Picker mode                                                                                                   |

**Appearance:**

| Option                               | Default | Description                                  |
| ------------------------------------ | ------- | -------------------------------------------- |
| `@pick_session_fzf_prompt`           | —       | Custom fzf prompt string                     |
| `@pick_session_fzf_ghost`            | —       | Custom fzf ghost text                        |
| `@pick_session_fzf_color`            | —       | Custom fzf color scheme                      |
| `@pick_session_fzf_options`          | —       | Extra fzf flags                              |
| `@pick_session_auto_rename_sessions` | `off`   | Auto-rename sessions to match expected names |

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

Grouped/sorted ordering is produced by `pick_session/filter.sh`:

1. **Session-backed repo/worktree groups** first (sessions first within each
   group, then related worktrees)
2. **Worktree-only groups** next
3. **Directory entries** at the end (clustered by scan root and path)

The picker uses fzf's native in-process filtering (no reload per keystroke)
across the visible label and a hidden match key column, with `--scheme=path` and
tie-breakers `begin,length,index`. Path-root matches (e.g., `~/work`) outrank
unrelated long-path hits. Queries like `work/kibana main` work.

### How caching works

- `pick_session/index_update.sh` builds the cache
  (`~/.cache/tmux/pick_session_items.tsv`) and a precomputed ordered snapshot
  (`pick_session_items_ordered.tsv`) in the background.
- Picker open prefers the ordered snapshot for instant first paint, validated
  against mutation/pending timestamps (bash `-nt` check, zero subprocess
  overhead).
- After `ctrl-x` kill or `alt-x` remove (which write mutation tombstones), the
  ordered snapshot is stale, so `pick_session/items.sh` runs with mutation
  filtering (~250 ms) to ensure killed/removed entries never reappear.
- `tmux_opt` reads are cached: a single `tmux show-options -g` call replaces
  multiple sequential round-trips.
- Picker open does not auto-reload (prevents visible rerender/churn); use
  `ctrl-r` for a fresh rebuild.

### How worktree discovery works

- Filesystem-based: scans configured roots for `.git` directories/files using
  `fd`.
- A directory containing a `.git` directory is treated as a "root checkout"; a
  directory containing a `.git` file is treated as a sibling worktree.
- Avoids expensive `git worktree list` calls and prevents external tool
  worktrees outside scan roots from leaking in.
- Directory rows stop at discovered worktree roots: nested subdirectories under
  a worktree are not emitted as `dir` rows.
- Home directory discovery is capped to depth `6`;
  `@pick_session_dir_exclude_file` and `@pick_session_dir_include_hidden`
  constrain scope.

### Session naming

- Worktree-backed session names use a filesystem-derived identifier: the "repo"
  part is the home-relative wrapper/repo path (e.g., `work/kibana` or
  `.backport/repositories/elastic/kibana`) and the "branch" part is the
  wrapper-relative remainder path (for layouts created by `,w`).
- For singular checkouts (no linked worktrees), the branch token uses the repo
  default branch (origin/upstream HEAD, then common defaults, finally `main`)
  regardless of current checkout.
- For remote-prefix wrappers, `<remote>/<branch...>` becomes
  `<remote>__<branch...>` for third-party remotes; first-party owners
  (origin/upstream owner match or your login) keep plain `<branch...>`.
- Names are sanitized to tmux-safe identifiers (e.g., `1.8` becomes `1_8`;
  slashes like `feat/foo` are preserved).
- Session entries do not render `#{session_path}` in the visible label
  (filtering is focused on the session name).
- The current session is marked `(current)` so it remains visible even after a
  rename.

### Popup performance

- Popup spawn temporarily overrides `default-shell` to `/bin/sh` during
  `display-popup` to avoid heavy-shell (fish, zsh with plugins) initialization
  overhead (~1 s). The original shell is restored atomically.
  `pick_session/pick_session.sh` itself runs under `bash` via its shebang.
- Both pickers run `fzf` with `FZF_DEFAULT_OPTS` cleared so global defaults
  don't distort the popup UI.
- For very large caches, `pick_session/filter.sh` automatically falls back to
  passthrough mode (default threshold `2000` rows); tune with
  `@pick_session_filter_passthrough_rows`.
- For very large caches, first paint can defer `dir` rows
  (`@pick_session_defer_dir_rows_threshold`).
- On `alt-x` remove, selecting a root checkout/worktree hides all impacted rows
  immediately (sibling worktrees and matching sessions).
- When the cache is empty, the picker falls back to tmux sessions + `zoxide`
  recent dirs (if installed) + `~`.
