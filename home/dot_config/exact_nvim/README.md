# Neovim Configuration

This directory contains my personal Neovim setup, managed with `chezmoi` and powered by [`lazy.nvim`](https://github.com/folke/lazy.nvim).

## Usage

1. `chezmoi apply`
2. Launch Neovim (`nvim`) and run `:Lazy sync` to install/update plugins.
3. Review `lua/core/options.lua`, `lua/core/keymaps.lua`, and the modules under `lua/plugins/` for customisation.
