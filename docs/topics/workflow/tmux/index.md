# Tmux

This setup is designed around a tmux-driven workflow.

If you are coming from VSCode/JetBrains, you can still use tmux incrementally. The lowest-disruption path is to use tmux for long-running sessions (servers, test watchers) while keeping your main editor unchanged.

## Config location

- [`home/dot_config/exact_tmux/readonly_tmux.conf`](../../../../home/dot_config/exact_tmux/readonly_tmux.conf)

This is a thin entrypoint that sources `conf.d` files in a fixed order.

## Notable choices

- prefix is `Ctrl-Space`
- vi copy-mode
- passthrough bindings for Neovim navigation
- no-prefix `C-S-h/j/k/l` are passed through as CSI-u sequences for terminal apps (Neovim)
- split config via [`home/dot_config/exact_tmux/conf.d/*.conf`](../../../../home/dot_config/exact_tmux/conf.d/*.conf)
- mouse on, `base-index 1`, renumber windows, focus events, aggressive resize

## Tmux config layout (`conf.d`)

Conventions:

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
- `42-gh-dash.conf`: GitHub picker popup (fzf-based, standalone config)
- `90-plugins.conf`: TPM plugin declarations + plugin options
- `99-tpm.conf`: TPM init (must stay last)

## Cheat sheet (this config)

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

## Tools and integrations

- Session picker (goto): `prefix` + `g`
- URL picker popup: `prefix` + `u`
- Session picker popup: `prefix` + `T`
- Command palette popup: `prefix` + `r` (`\,tmux-run-all`)
- GitHub picker popup: `prefix` + `G` (fzf PR/issue picker, standalone config; `alt-g` switches to/from session picker; `ctrl-s` switches work/home; `?` help)
- Agent prompt wrap: `Alt-Enter` (submits prompt with verification scaffold), `prefix` + `W` (toggle on/off)

For details:

- Popups + tools: [`docs/categories/tmux/popups-and-tools.md`](popups-and-tools.md)
- Pickers (URL/session/GitHub) + options: [`docs/categories/tmux/pickers.md`](pickers.md)
