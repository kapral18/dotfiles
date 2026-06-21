---
sidebar_position: 2
title: Git and quality of life
---

# Git and quality of life

## Git workflows

Hunks, blame, and history search live in:

- [`plugins/git.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_git.lua)

Highlights:

- gitsigns hunk navigation: `[h` / `]h`.
- stage/reset hunk mappings under `leader-gh*`.
- Diffview mappings under `leader-df*`.
- History search with `AdvancedGitSearch` under `leader-ga*`.

## Local plugins

This repo ships workflow-specific Lua plugins under:

- Source: [`plugins_local_src/`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src)
- Loaders: [`plugins_local/`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local)
- Load list: [`core/init.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_init.lua)

They cover testing, commit summarization, ownership/CODEOWNERS search, TypeScript export moves, tmux bridge, source/test toggling, code screenshots, quickfix, and window ergonomics.

Details: [Neovim local plugins](../local-plugins/index.md).

## Quality-of-life commands

Defined in [`core/keymaps.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_keymaps.lua):

| Command / mapping         | Purpose                                         |
| ------------------------- | ----------------------------------------------- |
| `:LargeFiles`             | Populate quickfix with very large tracked files |
| `:WW` / `:WWW`            | Write without triggering autocmds               |
| `leader-yp` / `leader-yP` | Copy relative / absolute path                   |
