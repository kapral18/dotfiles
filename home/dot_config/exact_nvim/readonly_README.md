# Neovim Configuration

This directory contains my personal Neovim setup, managed with `chezmoi`.

The config targets **Neovim 0.12+** and uses built-in `vim.pack` for plugin installation and updates, with trigger-aware deferred loading (`cmd`, `event`, `ft`, and key-triggered specs) handled by [`dash-paq.nvim`](https://github.com/kapral18/dash-paq.nvim), bootstrapped by `lua/core/init.lua` and configured with `lua/plugins/dash-paq.lua`.

For a guided tour (including an IDE-first on-ramp for VSCode/JetBrains users), see [`docs/topics/editor/neovim/index.md`](../../../docs/topics/editor/neovim/index.md).

## Implementation notes

- `lua/core/init.lua` bootstraps `dash-paq.nvim` onto `runtimepath` before calling its `setup()`: a local checkout at `~/code/dash-paq.nvim/main` (or a saved dev-toggle choice) if present, else `vim.pack.add` from GitHub.
- `plugin/` / `after/plugin/` sourcing uses Neovim's native load-plugins step; `dash-paq.nvim` relies on that step for its own deferred loading. `lua/core/options.lua` sets a guard global for each `$VIMRUNTIME/plugin/*` script that should stay inert; `matchit` (`g%`), `editorconfig`, and `osc52` load.

## Usage

1. Install the pinned version (`mise install neovim@0.12.2`).
2. `chezmoi apply`
3. Launch Neovim (`nvim`). Plugin management (dashboard, load trace, lockfile commands, version pinning) comes from [`dash-paq.nvim`](https://github.com/kapral18/dash-paq.nvim); see its README for commands and keys. This config maps `<leader>ll` (dashboard), `<leader>lL` (status), and `<leader>lt` (load trace). Run `:AutoSession save` (or `<localleader>ss`) to save sessions; the plugin's dashboard/trace popup buffers are transient and excluded from session save. Session search integrations are loaded on demand to improve startup time.
4. Review `exact_lua/exact_core/options.lua` and `exact_lua/exact_core/keymaps.lua` (installed as `lua/core/options.lua` and `lua/core/keymaps.lua`), and the modules under `exact_lua/exact_plugins/` (installed as `lua/plugins/`) for customization.
