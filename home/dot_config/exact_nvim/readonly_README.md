# Neovim Configuration

This directory contains my personal Neovim setup, managed with `chezmoi`.

The config targets **Neovim 0.12+** and uses built-in `vim.pack` for plugin installation and updates, with trigger-aware deferred loading (`cmd`, `event`, `ft`, and key-triggered specs) handled by `lua/core/plugins.lua`.

For a guided tour (including an IDE-first on-ramp for VSCode/JetBrains users), see [`docs/categories/editor-neovim.md`](../../../docs/categories/editor-neovim.md).

## Implementation notes

- The config sets `vim.opt.loadplugins = false` early (in `init.lua`) so Neovim does not auto-source `plugin/` / `after/plugin/` scripts for everything on `runtimepath`. This avoids double-sourcing and lets `lua/core/plugins.lua` fully control when plugin code is actually loaded.
- Built-in runtime packages needed for mappings (e.g. `matchit` for `g%`) are explicitly `packadd`'d.

## Usage

1. Install the pinned version (`asdf install neovim 0.12.0`).
2. `chezmoi apply`
3. Launch Neovim (`nvim`) and run `:PackDashboard` (or `<leader>ll`) for the floating plugin dashboard (status, risk, diff/repo links, single/multi/all updates, filter/sort/search), `:PackTrace` (or `<leader>lt`) to inspect deferred-load reasons, `:AutoSession save` (or `<localleader>ss`) to save sessions, or `:PackSync` for the raw `vim.pack` report. Dashboard/trace popup buffers are transient and excluded from session save. Session search integrations are loaded on demand to improve startup time.
4. Review `exact_lua/exact_core/options.lua` and `exact_lua/exact_core/keymaps.lua` (installed as `lua/core/options.lua` and `lua/core/keymaps.lua`), and the modules under `exact_lua/exact_plugins/` (installed as `lua/plugins/`) for customization.
