# Tmux: pickers

Back: [`docs/categories/tmux/index.md`](index.md)

This setup ships a URL picker and a session/worktree picker designed to run inside a tmux popup.

## Bindings

- URL picker popup: `prefix` + `u`
- Session picker popup: `prefix` + `T`

## Options (tmux `set -g`)

- URL picker:
  `@pick_url_history_limit` (default `screen`), `@pick_url_popup` (configured `center,60%,35%`; script fallback `center,100%,50%`), `@pick_url_fzf_flags`, `@pick_url_open_cmd`, `@pick_url_extra_filter`
- Pick session:
  `@pick_session_popup_height` (configured `70`; script default `40`), `@pick_session_popup_width` (configured `60`; script default `80`),
  `@pick_session_pre_refresh` (default `off`; set `on` to run cache update before fzf; off for snappy popup),
  `@pick_session_mode` (default `directory`),
  `@pick_session_github_login` (default empty; optional override for first-party remote owner detection),
  `@pick_session_fzf_options`, `@pick_session_fzf_prompt`, `@pick_session_fzf_ghost`, `@pick_session_fzf_color`,
  `@pick_session_auto_rename_sessions` (default `off`),
  `@pick_session_worktree_scan_roots` (default `~/work,~/code,~/.backport/repositories,~/.local/share`), `@pick_session_worktree_scan_depth` (default `6`),
  `@pick_session_cache_ttl` (default `60`), `@pick_session_cache_wait_ms` (default `0`), `@pick_session_mutation_tombstone_ttl` (default `300`), `@pick_session_session_tombstone_live_grace_s` (default `2`),
  `@pick_session_filter_passthrough_rows` (default `2000`; for caches at or above this row count, picker uses cache order directly and skips expensive regroup/sort),
  `@pick_session_defer_dir_rows_threshold` (default `0` = disabled; when set to a positive number and cache row count is at/above that threshold, first paint omits `dir` rows to reduce open latency),
  `@pick_session_live_refresh_ttl` (default `20`), `@pick_session_live_refresh_interval_ms` (default `1500`), `@pick_session_live_refresh_start_delay_ms` (default `5000`),
  `@pick_session_live_refresh_pause_on_multi` (default `on`), `@pick_session_live_refresh_pause_on_query` (default `on`),
  `@pick_session_dir_exclude_file` (default `~/.config/tmux/pick_session_dir_exclude.txt`), `@pick_session_dir_include_hidden` (default `on`)

## Notes

- `pick_url.sh` and `pick_session.sh` run `fzf` with `FZF_DEFAULT_OPTS` cleared so global defaults (height/preview/etc.) don't distort the popup UI. Use the `@pick_*` options above to customize.
- `pick_url` de-duplicates path-prefix URLs, so if both `https://site/x` and `https://site/x/y` are detected, it keeps the deeper path entry.
- `pick_session` entries render with ANSI colors and Nerd Font icons (`session`, `worktree`, `dir`) in the first column; `fzf` is run with `--ansi` so filtering still works on the visible text.
- `pick_session` also styles the input line (`--prompt`, `--ghost`, `--color`) by default. Use `@pick_session_fzf_prompt`, `@pick_session_fzf_ghost`, or `@pick_session_fzf_color` to customize, and `@pick_session_fzf_options` for any extra `fzf` flags.
- Full refresh indexes configured scan roots plus `$HOME` by default. Home directory discovery is capped to depth `6` so root folders and practical descendants remain discoverable without unbounded crawl cost; `@pick_session_dir_exclude_file` and `@pick_session_dir_include_hidden` constrain scope.
- Excludes are file-backed (`@pick_session_dir_exclude_file`). The file uses `.gitignore` syntax (passed to `fd` via `--ignore-file`); trailing `/` marks directory-recursive excludes, `#` comments are supported.
- Directory rows intentionally stop at discovered worktree roots: once a folder is identified as a worktree/session path, nested subdirectories under it are not emitted as `dir` rows.
- When the cache is empty, the picker falls back to tmux sessions + `zoxide` recent dirs (if installed) + `~`.
- Grouped/sorted ordering is produced by `pick_session_filter.sh`:
  - session-backed repo/worktree groups first (sessions first within group, then related worktrees)
  - worktree-only groups next
  - `dir` entries at the end (still clustered by scan root and path)
- `pick_session_index_update.sh` also maintains `~/.cache/tmux/pick_session_items_ordered.tsv` (precomputed ordered snapshot) in the background.
- Picker open prefers the ordered snapshot for instant + stable first paint, but validates it against mutation/pending timestamps first (bash `-nt` check, zero subprocess overhead).
- For very large caches, first paint can defer `dir` rows and render only `session`/`worktree` rows. This is disabled by default (`@pick_session_defer_dir_rows_threshold` = `0`); set to a positive row count to enable.
- Popup spawn temporarily overrides `default-shell` to `/bin/sh` during `display-popup` creation to avoid heavy-shell (fish, zsh with plugins) initialization overhead (~1 s with fish). The original shell is restored atomically in the same tmux command chain. `pick_session.sh` itself runs under `bash` via its shebang.
- `tmux_opt` reads in `pick_session.sh` are cached: a single `tmux show-options -g` call replaces multiple sequential `tmux show-option` round-trips.
- First paint comes from `pick_session_items_ordered.tsv` when fresh; after `ctrl-x` kill or `alt-x` remove (which write mutation tombstones), the ordered snapshot is stale so `pick_session_items.sh` runs with mutation filtering (~250 ms) to ensure killed/removed entries never reappear.
- Picker open does not auto-reload anymore (prevents visible rerender/churn); use `ctrl-r` (or `alt-r` for force refresh) when you want a fresh full rebuild while the picker is open.
- Picker `ctrl-r` refresh keeps grouped ordering (`pick_session_filter.sh --refresh --force-order`) while still triggering quick+full background cache refresh.
- For very large caches, `pick_session_filter.sh` automatically falls back to passthrough mode (default threshold `2000` rows) so popup open latency stays low; tune with `@pick_session_filter_passthrough_rows`.
- The picker uses fzf's native in-process filtering (no reload per keystroke) across the visible label and the hidden match key column, with `--scheme=path` and tie-breakers `begin,length,index` so path-root matches (for example `~/work`) outrank unrelated long-path text hits. Queries like `work/kibana main` match.
- The picker de-duplicates rows by path: for the same path, it shows only one of `session` / `worktree` / `dir` (priority `session` → `worktree` → `dir`).
- On `alt-x` remove, selecting a root checkout/worktree now hides all impacted rows immediately (sibling worktrees and matching sessions), instead of only hiding the single selected row while cleanup is still running.
- Worktree-backed session names use a filesystem-derived identifier: the “repo” part is the home-relative wrapper/repo path (for example `work/kibana` or `.backport/repositories/elastic/kibana`) and the “branch” part is the wrapper-relative remainder path (for wrapper layouts created by `,w`). For singular checkouts (no linked worktrees), the branch token uses the repo default branch (origin/upstream HEAD, then common defaults, finally `main`) regardless of current checkout. For remote-prefix wrappers, `<remote>/<branch...>` becomes `<remote>__<branch...>` for third-party remotes, but first-party owners (origin/upstream owner match or your own login) keep plain `<branch...>`.
- Session entries do not render `#{session_path}` in the visible label (filtering is focused on the session name).
- Worktree discovery is filesystem-based: it scans configured roots for `.git` directories/files. The directory containing a `.git` directory is treated as a “root checkout”, and directories containing a `.git` file are treated as sibling worktrees. This avoids expensive `git worktree list` calls and prevents external tool worktrees outside scan roots from leaking into the picker.
- When creating sessions from worktrees/dirs, names are sanitized to tmux-safe identifiers so tmux doesn’t silently rename them and break switching (for example branch names like `1.8` become `1_8`; slashes like `feat/foo` are preserved).
- The picker includes the current session (marked `(current)`), so renaming a session from inside it doesn’t make it “disappear” from the picker.
