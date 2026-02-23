# Terminals And Tmux

Back: [`docs/categories/index.md`](index.md)

This setup is designed around a tmux-driven workflow.

If you are coming from VSCode/JetBrains, you can still use tmux incrementally.
The lowest-disruption path is to use tmux for long-running sessions (servers,
test watchers) while keeping your main editor unchanged.

## Terminal

Default terminal emulator config:

- `home/dot_config/exact_ghostty/config`

## Bat (Better `cat`)

- Config: `home/dot_config/bat/config`

Themes are pulled via externals into:

- `~/.config/bat/themes`

See `home/.chezmoiexternal.toml`.

## Tmux

- Config: `home/dot_config/tmux/tmux.conf`

Notable choices:

- prefix is `Ctrl-Space`
- vi copy-mode
- passthrough bindings for Neovim navigation

## Tmux Cheat Sheet (This Config)

These are implemented in `home/dot_config/tmux/tmux.conf`.

- Prefix: `Ctrl-Space`
- Reload config: `prefix` then `R`
- Toggle zoom (maximize pane): `prefix` then `f`
- Kill pane: `prefix` then `x`
- Kill window: `prefix` then `&`

There is also a popup bound to `prefix` then `r` that runs `,tmux-run-all`.

Custom commands live under `home/exact_bin/`.

If you are new to tmux, learn these first:

- create window/pane
- switch between panes
- copy-mode basics

Then adopt the repo-specific stuff (prefix, plugins, extra keybinds).

## tmux plugin manager (TPM)

TPM is pulled via externals:

- `home/.chezmoiexternal.toml`

The tmux config loads it from (for theme + continuum + resurrect):

- `~/.config/tmux/plugins/tpm/tpm`

## Custom tmux Tools

Small tmux helpers implemented directly in this repo (bindings + scripts).

Entry point:

- `home/dot_config/tmux/conf.d/40-tools.conf`

Scripts:

- `home/dot_config/tmux/scripts/`

Options (tmux `set -g`):

- URL picker:
  `@pick_url_history_limit` (default `screen`), `@pick_url_popup` (default `center,100%,50%`), `@pick_url_fzf_flags`, `@pick_url_open_cmd`, `@pick_url_extra_filter`
- Pick session:
  `@pick_session_popup_height` (default `40`), `@pick_session_popup_width` (default `80`),
  `@pick_session_mode` (default `directory`),
  `@pick_session_fzf_options`, `@pick_session_fzf_prompt`, `@pick_session_fzf_ghost`, `@pick_session_fzf_color`,
  `@pick_session_worktree_scan_roots` (default `~/work,~/code,~/.local/share`), `@pick_session_worktree_scan_depth` (default `6`),
  `@pick_session_cache_ttl` (default `60`), `@pick_session_cache_wait_ms` (default `0`), `@pick_session_mutation_tombstone_ttl` (default `300`),
  `@pick_session_live_refresh_ttl` (default `5`), `@pick_session_live_refresh_interval_ms` (default `1500`), `@pick_session_live_refresh_start_delay_ms` (default `700`),
  `@pick_session_live_refresh_pause_on_multi` (default `on`), `@pick_session_live_refresh_pause_on_query` (default `on`),
  `@pick_session_dir_max_depth` (default `4`), `@pick_session_dir_exclude` (default `.git,.git/*,.git/**`), `@pick_session_dir_include_hidden` (default `on`)

Notes:

- `pick_url.sh` and `pick_session.sh` run `fzf` with `FZF_DEFAULT_OPTS` cleared so global defaults (height/preview/etc.) don't distort the popup UI. Use the `@pick_*` options above to customize.
- `pick_session` entries render with ANSI colors and Nerd Font icons (`session`, `worktree`, `dir`) in the first column; `fzf` is run with `--ansi` so filtering still works on the visible text.
- `pick_session` also styles the input line (`--prompt`, `--ghost`, `--color`) by default. Use `@pick_session_fzf_prompt`, `@pick_session_fzf_ghost`, or `@pick_session_fzf_color` to customize, and `@pick_session_fzf_options` for any extra `fzf` flags.
- Plain `dir` entries (the fallback home-directory list) are path-sorted before rendering, so siblings/ancestors stay grouped instead of appearing in traversal order.
- Plain `dir` entries are scanned with `fd` (no `find` fallback).
- While the query is empty, the picker preserves source order (session/worktree grouping + path-sorted `dir` entries). Once you type, `fzf` re-ranks results by fuzzy score; `pick_session` uses `fzf --scheme=path --filepath-word` so path-heavy entries sort more naturally.
- `pick_session.sh` loads from a cached list for fast startup. If the cache is missing, the item source now kicks only a quick-only background refresh first (seeded + worktrees) and falls back immediately, so popup open is not blocked by a full index build. The live refresher also starts with a quick-only pass and defers full refreshes to later loop iterations; the open `fzf` picker is updated automatically when cache refreshes finish (query/filter text is preserved by `fzf` reload). Cache refresh publishes in two stages (quick seeded list, then full list) so the open picker can populate without waiting for the full recursive scan. Live auto-refresh pauses while you have a multi-selection active or a non-empty query (to avoid wiping selections / active filtering) and resumes afterward. Use `ctrl-r` to reload the cached list immediately, and `alt-r` to force a background refresh and push the new results into the open picker.
- Picker removals write short-lived tombstones (`session target` / `path prefix`) that are applied both when reading the cache and when publishing scan results, which prevents long-running in-flight reindexes from resurrecting removed entries. `@pick_session_mutation_tombstone_ttl` controls how long those tombstones are kept.
- Hidden directories are included in the plain home-directory list by default (`@pick_session_dir_include_hidden on`). Worktree discovery scans hidden directories under `@pick_session_worktree_scan_roots` (with `fd --hidden`); the default roots include `~/.local/share` for hidden worktree hubs, and those roots are seeded into the quick refresh stage for immediate matching.
- Worktree repo groups are ordered by bucket (`has session` first) and then by configured scan-root order/path (`@pick_session_worktree_scan_roots`), so `~/work` / `~/code` / `~/.local/share` stay clustered instead of being mixed by repo name.
- `ctrl-x` kills selected tmux sessions. `alt-x` removes selected worktrees (non-blocking; runs `,w remove` in the background).
- The picker prioritizes repo groups with sessions, then repo groups with worktrees (no sessions yet), then non-worktree sessions, and finally plain directories under `~`.

## Session Restore (Resurrect)

This setup uses `tmux-resurrect`, but filters restores down to the last 5 most
recently active sessions to keep restore fast (filtering happens *before* the
restore starts, via a `tmux-resurrect` pre-restore hook).

Config:

- `home/dot_config/tmux/conf.d/90-plugins.conf`
- `home/dot_config/tmux/scripts/executable_resurrect_keep_last_sessions.sh`

To change the limit, update `@resurrect_keep_sessions`.

## Lowfi (Music In tmux)

This setup includes a small integration that runs `lowfi` inside a dedicated
tmux session.

- Command: `home/exact_bin/executable_,tmux-lowfi` (installs as `,tmux-lowfi`)

Tracklist data is pulled via externals into:

- `~/Library/Application Support/lowfi`

See `home/.chezmoiexternal.toml`.

## Verification And Troubleshooting

Basic checks:

```bash
tmux -V
tmux list-sessions
command -v ,w
command -v ,tmux-run-all
command -v ,tmux-lowfi
```

If tmux config changes are not reflected:

```bash
tmux source-file ~/.config/tmux/tmux.conf
```

If plugin behavior is missing:

- confirm TPM exists under `~/.config/tmux/plugins/tpm`.
- open tmux and install/update plugins via TPM.

## Related

- Lowfi in tmux: [`docs/recipes/lowfi-in-tmux.md`](../recipes/lowfi-in-tmux.md)
- Worktree workflow: [`docs/recipes/worktree-workflow.md`](../recipes/worktree-workflow.md)
