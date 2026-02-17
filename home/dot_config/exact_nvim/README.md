# Neovim Configuration

This directory contains my personal Neovim setup, managed with `chezmoi` and powered by [`lazy.nvim`](https://github.com/folke/lazy.nvim).

For a guided tour (including an IDE-first on-ramp for VSCode/JetBrains users), see [`docs/categories/editor-neovim.md`](../../../docs/categories/editor-neovim.md).

## Usage

1. `chezmoi apply`
2. Launch Neovim (`nvim`) and run `:Lazy sync` to install/update plugins.
3. Review `exact_lua/exact_core/options.lua` and
   `exact_lua/exact_core/keymaps.lua` (installed as `lua/core/options.lua` and
   `lua/core/keymaps.lua`), and the modules under `exact_lua/exact_plugins/`
   (installed as `lua/plugins/`) for customization.
