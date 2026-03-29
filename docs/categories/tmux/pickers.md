# Tmux: pickers

Back: [`docs/categories/tmux/index.md`](index.md)

This setup ships a URL picker, a session/worktree picker, and a GitHub picker
(PRs/issues) designed to run inside tmux popups.

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
| `alt-y`            | Copy underlying path(s) to clipboard                                                                      |
| `ctrl-s`           | **Send command** — enters a modal: type a command, `enter` sends it to selected session(s), `esc` cancels |
| `ctrl-r`           | Refresh list (grouped ordering + background cache rebuild)                                                |
| `alt-r`            | Force full refresh                                                                                        |
| `alt-p`            | Open PR in browser (if the entry's branch has a linked PR)                                                |
| `alt-i`            | Open issue in browser (if the entry's branch references an issue number)                                  |
| `alt-g`            | Switch to GitHub picker (PRs/issues)                                                                      |
| `ctrl-/`           | Toggle preview panel visibility                                                                           |
| `?`                | Show keybinding help in the preview panel                                                                 |
| `shift-up/down`    | Scroll preview (line)                                                                                     |
| `shift-left/right` | Scroll preview (page)                                                                                     |

### Switching between pickers

`alt-g` switches between the session picker and the GitHub picker. The current
popup closes and a new one opens with the correct dimensions (session picker
uses configured `@pick_session_popup_*` sizes, GitHub picker uses 95%×95%). The
loop logic lives in the outer wrapper scripts (`popup.sh` / `gh_popup.sh`), not
in the inner picker scripts, because `tmux resize-popup` is not available.

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
- Dirty detection runs in parallel (half available cores) during the background
  index.
- Status flags are stored in the cache `meta` column (`status=dirty`,
  `status=stale`, etc.) and survive rehydration.

### GitHub PR/issue badges

For non-default branches, the indexer queries `gh` to detect linked pull
requests and issues. Badges appear inline after status badges.

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

- **PR detection**:
  `gh pr view --json number,state,url,reviewDecision,closingIssuesReferences`
  with `cwd` set to the worktree path (infers repo and branch from git context).
- **Issue detection** (resolved in order, first match wins):
  1. `comma.w.issue.number` worktree-local git config (set by `,w`)
  2. Branch name suffix heuristic (`-NNN` or `/NNN`, e.g. `fix/1234-desc` →
     issue `1234`)
  3. PR `closingIssuesReferences` — issues linked via `Closes #N`, `Fixes #N`,
     etc. in the PR description (extracted from the same `gh pr view` call, zero
     extra network cost). The exact `owner/repo` from the reference is used as
     the `-R` override for `gh issue view`, so cross-repo closing issues and
     fork workflows resolve correctly without relying on `cwd` inference. Once a
     number is found, `gh issue view <num>` fetches the current state.
- Lookups run in parallel (half available cores) during the background index,
  adding no latency to picker open.
- Results are cached on disk (`~/.cache/tmux/pick_session_gh.json`) with smart
  TTLs: open items refresh every 10 min, merged/closed items every 24 h, cache
  misses every 1 h. Branch or remote changes invalidate immediately. Stale
  worktree paths are pruned on each write.
- PR/issue metadata is stored in the TSV cache `meta` column
  (`pr=NUMBER:STATE:REVIEW:CI:URL`, `issue=NUMBER:STATE:URL`). `REVIEW` is the
  PR review decision (`APPROVED`, `CHANGES_REQUESTED`, `REVIEW_REQUIRED`, or
  empty). `CI` is the CI status (`SUCCESS`, `FAILURE`, `PENDING`, or empty).
- The preview pane shows PR/issue details (number, state, review status, URL) at
  the top for session and worktree entries.
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

Grouped/sorted ordering is produced by `pickers/session/filter.sh`:

1. **Session-backed repo/worktree groups** first (sessions first within each
   group, then related worktrees)
2. **Worktree-only groups** next
3. **Directory entries** at the end (clustered by scan root and path)

The picker uses fzf's native in-process filtering (no reload per keystroke)
across the visible label and a hidden match key column, with `--scheme=path` and
tie-breakers `begin,length,index`. Path-root matches (e.g., `~/work`) outrank
unrelated long-path hits. Queries like `work/kibana main` work.

### How caching works

- `pickers/session/index_update.sh` builds the cache
  (`~/.cache/tmux/pick_session_items.tsv`) and a precomputed ordered snapshot
  (`pick_session_items_ordered.tsv`) in the background.
- Picker open prefers the ordered snapshot for instant first paint, validated
  against mutation/pending timestamps (bash `-nt` check, zero subprocess
  overhead).
- After `ctrl-x` kill or `alt-x` remove (which write mutation tombstones), the
  ordered snapshot is stale, so `pickers/session/items.sh` runs with mutation
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
  `pickers/session/pick_session.sh` itself runs under `bash` via its shebang.
- The session picker and GitHub picker run `fzf` with `SHELL=bash` so preview /
  execute commands don't pay fish startup cost on every selection change.
- All pickers (URL, session, GitHub) run `fzf` with `FZF_DEFAULT_OPTS` cleared
  so global defaults don't distort the popup UI.
- For very large caches, `pickers/session/filter.sh` automatically falls back to
  passthrough mode (default threshold `2000` rows); tune with
  `@pick_session_filter_passthrough_rows`.
- For very large caches, first paint can defer `dir` rows
  (`@pick_session_defer_dir_rows_threshold`).
- On `alt-x` remove, selecting a root checkout/worktree hides all impacted rows
  immediately (sibling worktrees and matching sessions).
- `alt-x` removal will **not** tear down the active tmux session unless you
  explicitly selected it (prevents “remove sibling worktree” from killing the
  current session).
- When the cache is empty, the picker falls back to tmux sessions + `zoxide`
  recent dirs (if installed) + `~`.

---

## GitHub picker

A standalone fzf-based PR/issue picker. It reads PR and issue sections from its
own YAML configs and displays them in `fzf` with rich preview, worktree markers,
and review status badges. gh-dash is not a dependency.

### Bindings

| Key                | Action                                            |
| ------------------ | ------------------------------------------------- |
| `prefix` + `G`     | Open GitHub picker popup (95%×95%)                |
| `enter`            | Checkout worktree + focus (batch if items marked) |
| `alt-b`            | Checkout + open Octo review (PRs only)            |
| `ctrl-t`           | Batch worktree create (marked items)              |
| `alt-o`            | Open in browser                                   |
| `alt-y`            | Copy URL(s) to clipboard                          |
| `tab`              | Mark/unmark item (multi-select)                   |
| `alt-space`        | Mark/unmark item (alternate toggle)               |
| `ctrl-s`           | Switch work/home mode                             |
| `ctrl-r`           | Refresh from GitHub (current mode)                |
| `alt-g`            | Switch to session picker                          |
| `alt-c`            | New comment (opens `$EDITOR`)                     |
| `alt-r`            | Quote-reply a comment                             |
| `alt-d`            | Edit your own comment                             |
| `alt-e`            | Cycle preview: collapsed → body → all expanded    |
| `ctrl-/`           | Toggle preview                                    |
| `?`                | Show keybinding help                              |
| `alt-j` / `alt-k`  | Page down / up                                    |
| `shift-up/down`    | Scroll preview (line)                             |
| `shift-left/right` | Scroll preview (page)                             |

### Entry source

Items come from the gh picker's standalone config files
(`~/.config/tmux/scripts/pickers/github/gh-picker-work.yml` and
`~/.config/tmux/scripts/pickers/github/gh-picker-home.yml`). Each file defines
`prSections` and `issuesSections` with `title` and `filters` (GitHub Search
syntax). The Python fetcher (`lib/gh_items_main.py`) parses these YAML files,
runs GitHub Search API queries, and formats results as `fzf`-consumable TSV.

In work mode, the default config separates PRs that request **your** review
(excluding those already in your team queue) from PRs that request **team**
review, so the sections stay meaningfully distinct while global dedupe remains
useful.

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

Review and CI badges are fetched via a batched GraphQL call that piggybacks on
the section fetch, at zero extra round-trip cost.

The conflict badge is also sourced from GraphQL (`mergeable=CONFLICTING`). If
GraphQL metadata is temporarily unavailable during a refresh, the picker keeps
the last-known conflict badge until fresh metadata is fetched; in that case the
badge is shown **dim** to indicate it may be stale (use `ctrl-r` to force
revalidation).

Similarly, when GraphQL metadata is temporarily unavailable, the picker may show
last-known **review** / **CI** badges in a **dim** style rather than dropping
them abruptly.

### Worktree detection

The picker detects whether a PR or issue has a local worktree using a 3-tier
heuristic:

1. `comma.w.issue.number` worktree-local git config (authoritative, set by `,w`)
2. Branch name suffix extraction (`-NNN` or `/NNN`)
3. Batched GraphQL `headRefName` matching against local worktree branches
   (catches PRs checked out by `,w prs`)

For issues, the picker also treats an issue as "local" when it is linked from an
existing session/worktree entry in the session picker cache (e.g. via PR
closing-issue references). This keeps issue indicators consistent across
pickers.

### Actions

- **`enter` (no marks)**: single-item checkout. On a PR, runs
  `,w prs --focus <number>`; on an issue, runs `,w issue --focus <number>`
  (interactive branch prompt if the worktree doesn't exist yet). Exits the
  picker.
- **`enter` (items marked)**: batch worktree creation for all marked items (same
  as `ctrl-t`). PRs are created automatically; issues open `$EDITOR` with a
  batch naming buffer. Stays in the picker.
- **`ctrl-t`**: explicit batch worktree creation (same as `enter` with marks).
- **`alt-b` on a PR**: same as single `enter`, then opens Octo review in a new
  tmux window.
- **`alt-o`**: opens the PR/issue URL in the browser.
- **`alt-y`**: copies the URL(s) to the clipboard.
- **`alt-c`**: new comment — opens `$EDITOR`, posts on save.
- **`alt-r`**: quote-reply — pick a comment via fzf, quote it, open `$EDITOR`.
- **`alt-d`**: edit own comment — pick one of your comments via fzf, edit in
  `$EDITOR`.
- If the repo does not exist locally, `,gh-tfork` bootstraps it first.

### Cache

- TTL: 300 seconds (5 minutes).
- Cache file: `~/.cache/tmux/gh_picker_{work,home}.tsv`.
- `ctrl-r` forces a refresh bypassing the cache.

### Preview pane

Shows PR/issue details: state, review decision, branches, author/assignee,
changed files, labels, and body text. Uses `gh pr view` / `gh issue view` with
`bat` for Markdown rendering. For PRs, it also shows `mergeable` (e.g.
`MERGEABLE`, `CONFLICTING`) so the preview stays authoritative even if list
badges are stale.

### Popup dimensions

The GitHub picker popup opens at 95%×95%. When switching to the session picker
via `alt-g`, the popup closes and reopens at the session picker's configured
dimensions. See [Switching between pickers](#switching-between-pickers) above.
