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
- no-prefix `C-S-h/j/k/l` are passed through as CSI-u sequences for terminal apps (Neovim)
- split config via `home/dot_config/tmux/conf.d/*.conf`
- mouse on, `base-index 1`, renumber windows, focus events, aggressive resize

## Tmux Config Layout (`conf.d`)

Keep the split config. `home/dot_config/tmux/tmux.conf` is a thin entrypoint that
only sources `conf.d` files in a fixed order.

Conventions (recommended / current):

- `tmux.conf` stays source-only (no feature logic mixed in)
- numeric prefixes define load order and are the contract
- one concern per file (base, keys, copy-mode, integrations, tools, plugins)
- feature bindings and feature options should live in the same file when possible
- `90-plugins.conf` declares plugin options/plugins; `99-tpm.conf` remains TPM bootstrap only
- add new files by range, not by appending random names:
  - `00-39`: core tmux behavior and global keymaps
  - `40-89`: custom tools / popups / integrations
  - `90-99`: plugin declarations and TPM init

Current file map:

- `00-base.conf`: tmux defaults / terminal features / mouse / indexing / env
- `10-prefix-and-global-keys.conf`: prefix, global key behavior, swap key-table, reload popup
- `11-pane-and-window-nav.conf`: pane/window navigation, resize, split, and path-aware new-window
- `20-copy.conf`: copy-mode (vi) + mouse copy overrides
- `30-lowfi.conf`: lowfi integration hotkeys
- `40-session-tools.conf`: session helper bindings (`goto/new/promote/join/kill`)
- `41-pickers.conf`: URL/session picker bindings + picker-related tmux options
- `90-plugins.conf`: TPM plugin declarations + plugin options
- `99-tpm.conf`: TPM init (must stay last)

## Tmux Cheat Sheet (This Config)

These are implemented by `home/dot_config/tmux/tmux.conf` plus
`home/dot_config/tmux/conf.d/*.conf`.

- Prefix: `Ctrl-Space`
- Reload config: `prefix` then `R`
- Toggle zoom (maximize pane): `prefix` then `f`
- Kill pane: `prefix` then `x`
- Kill window: `prefix` then `&`
- Pane navigation: `prefix` + `h/j/k/l` (also `prefix` + `C-h/C-j/C-k/C-l`)
- Pane resize: `prefix` + `H/J/K/L` (step uses `@pane_resize`, fallback `5`)
- Swap windows: `prefix` + `<` / `>`
- New window in current pane path: `prefix` + `c`
- Split in current pane path: `prefix` + `|` / `-` (also `%` / `"`)
- Force full split in current pane path: `prefix` + `\\` / `_`
- Copy-mode (vi): `v` begin selection, `C-v` rectangle toggle, `y` copy without clearing; mouse drag/double/triple click copy is overridden to avoid cursor jump

There is also a popup bound to `prefix` then `r` that runs `,tmux-run-all`.

Session / picker bindings from `home/dot_config/tmux/conf.d/40-session-tools.conf` and `home/dot_config/tmux/conf.d/41-pickers.conf`:

- Goto session picker: `prefix` + `g`
- Switch to last session: `prefix` + `S`
- New session prompt: `prefix` + `C`
- Promote current pane to session/window: `prefix` + `@` / `prefix` + `C-@`
- Join pane flow: `prefix` + `t` (then `h`/`%`/`|`, `v`/`"`/`-`, or `f`/`@`)
- Kill session prompt: `prefix` + `X`
- URL picker popup: `prefix` + `u`
- Session picker popup: `prefix` + `T`

Swap key-table (from `prefix` + `s`):

- `h` / `l`: swap pane left/right
- `H` / `L`: swap window left/right

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

Configured plugin options (`home/dot_config/tmux/conf.d/90-plugins.conf`):

- `@plugin` entries: TPM, Catppuccin, Continuum, Resurrect
- `@catppuccin_flavor 'frappe'`
- `@continuum-restore 'on'`
- `@continuum-save-interval '15'`
- `@resurrect_keep_sessions '5'`
- `@resurrect-hook-post-save-all` and `@resurrect-hook-pre-restore-all` point to `~/.config/tmux/scripts/resurrect_keep_last_sessions.sh`

## Custom tmux Tools

Small tmux helpers implemented directly in this repo (bindings + scripts).

Entry points:

- `home/dot_config/tmux/conf.d/40-session-tools.conf`
- `home/dot_config/tmux/conf.d/41-pickers.conf`

Scripts:

- `home/dot_config/tmux/scripts/`

Options (tmux `set -g`):

- URL picker:
  `@pick_url_history_limit` (default `screen`), `@pick_url_popup` (configured `center,60%,35%`; script fallback `center,100%,50%`), `@pick_url_fzf_flags`, `@pick_url_open_cmd`, `@pick_url_extra_filter`
- Pick session:
  `@pick_session_popup_height` (default `40`), `@pick_session_popup_width` (configured `60`; script default `80`),
  `@pick_session_mode` (default `directory`),
  `@pick_session_fzf_options`, `@pick_session_fzf_prompt`, `@pick_session_fzf_ghost`, `@pick_session_fzf_color`,
  `@pick_session_worktree_scan_roots` (default `~/work,~/code,~/.local/share`), `@pick_session_worktree_scan_depth` (default `6`),
  `@pick_session_cache_ttl` (default `60`), `@pick_session_cache_wait_ms` (default `0`), `@pick_session_mutation_tombstone_ttl` (default `300`), `@pick_session_session_tombstone_live_grace_s` (default `2`),
  `@pick_session_live_refresh_ttl` (default `20`), `@pick_session_live_refresh_interval_ms` (default `1500`), `@pick_session_live_refresh_start_delay_ms` (default `5000`),
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
- Picker removals write short-lived tombstones (`session target` / `path prefix`) that are applied both when reading the cache and when publishing scan results, which prevents long-running in-flight reindexes from resurrecting removed entries. `@pick_session_mutation_tombstone_ttl` controls how long those tombstones are kept. `@pick_session_session_tombstone_live_grace_s` controls how long a freshly killed session name is hidden from the live tmux session overlay (used for immediate `ctrl-x` optimistic hide without hiding recreated sessions for minutes).
- Hidden directories are included in the plain home-directory list by default (`@pick_session_dir_include_hidden on`). Worktree discovery scans hidden directories under `@pick_session_worktree_scan_roots` (with `fd --hidden`); the default roots include `~/.local/share` for hidden worktree hubs, and those roots are seeded into the quick refresh stage for immediate matching.
- Worktree repo groups are ordered by bucket (`has session` first) and then by configured scan-root order/path (`@pick_session_worktree_scan_roots`), so `~/work` / `~/code` / `~/.local/share` stay clustered instead of being mixed by repo name.
- `ctrl-x` kills selected tmux sessions. `alt-x` removes selected worktrees (non-blocking; runs `,w remove` in the background).
- Multi-select `Enter` creates new sessions in a deferred mode (placeholder panes). When you enter one of these sessions, a tmux `client-session-changed` hook respawns the pane into your real shell and applies the 2-pane layout. This avoids rendering many prompts at once for heavy repos (for example Kibana worktrees).
- `pick_session_items.sh` re-groups worktree-backed rows against the live tmux session list on read, so newly opened worktrees are promoted into the repo group’s session-first block immediately (and `ctrl-x` demotes them back to `worktree`/`dir` rows after the kill completes) without waiting for reindex timing/TTL.
- The picker prioritizes repo groups with sessions, then repo groups with worktrees (no sessions yet), then non-worktree sessions, and finally plain directories under `~`.

## Session Restore (Resurrect)

This setup uses `tmux-resurrect`, but filters restores down to the last 5 most
recently active sessions to keep restore fast (filtering happens *before* the
restore starts, via a `tmux-resurrect` pre-restore hook).

Config:

- `home/dot_config/tmux/conf.d/90-plugins.conf`
- `home/dot_config/tmux/scripts/executable_resurrect_keep_last_sessions.sh`

To change the limit, update `@resurrect_keep_sessions`.

The restore filter script also respects `@resurrect-dir` (if set by
`tmux-resurrect`) when locating the latest resurrect file.

## Lowfi (Music In tmux)

This setup includes a small integration that runs `lowfi` inside a dedicated
tmux session.

- Command: `home/exact_bin/executable_,tmux-lowfi` (installs as `,tmux-lowfi`)
- Global keys (no tmux prefix): `F10` play/pause, `F11` skip, `F12` next tracklist

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

If custom session pickers or URL picker behave oddly:

- `bash -n ~/.config/tmux/scripts/pick_session.sh ~/.config/tmux/scripts/pick_session_items.sh ~/.config/tmux/scripts/pick_session_live_refresh.sh ~/.config/tmux/scripts/pick_url.sh`
- `tmux source-file ~/.config/tmux/tmux.conf`

## Related

- Lowfi in tmux: [`docs/recipes/lowfi-in-tmux.md`](../recipes/lowfi-in-tmux.md)
- Worktree workflow: [`docs/recipes/worktree-workflow.md`](../recipes/worktree-workflow.md)
