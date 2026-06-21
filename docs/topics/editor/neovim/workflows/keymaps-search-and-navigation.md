---
sidebar_position: 1
title: Keymaps, search, and navigation
---

# Keymaps, search, and navigation

## Discovering keymaps

This config installs `which-key`:

- [`plugins/which-key.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_which-key.lua)

Most mappings are defined with descriptions in:

- [`core/keymaps.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_keymaps.lua)

If you forget a shortcut, use `which-key` and leader mappings as the primary discovery mechanism.

## Starter keymaps

| Area                   | Keys                                                                                                                 |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Window navigation      | `Ctrl-h/j/k/l`; `leader-<bar>` split right; `leader--` split below                                                   |
| Buffers                | `leader-bb` or ``leader-` `` toggles last buffer; `[b` / `]b` move buffers                                           |
| Search                 | `leader-Space` files; `leader-sg` live grep; `leader-/` current buffer grep                                          |
| Explorer               | `leader-e` Neo-tree cwd; `leader-ge` Neo-tree git status                                                             |
| Diagnostics / quickfix | `leader-cd`, `[d`, `]d`, `leader-xq`, `leader-xl`                                                                    |
| Git hunks              | `[h`, `]h`, `leader-ghp`                                                                                             |
| GitHub / Octo          | `leader-goa`, `leader-goil`, `leader-gois`, `leader-gopl`, `leader-gops`, `leader-godl`, `leader-gonl`, `leader-gos` |

## Search and navigation

Repo search is centered around `fzf-lua`:

- [`plugins/fzf.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_fzf.lua)

High-signal mappings:

| Mapping     | Scope                              |
| ----------- | ---------------------------------- |
| `leader-sg` | Live grep in cwd                   |
| `leader-se` | Grep changed lines from git status |
| `leader-sE` | Grep changed lines from branch     |
| `leader-sf` | Grep changed files from git status |
| `leader-sF` | Grep changed files from branch     |

File explorers:

- Neo-tree: [`plugins/neo-tree.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_neo-tree.lua)
- Yazi: same file (`mikavilpas/yazi.nvim`)
- Oil: same file (`stevearc/oil.nvim`)

Useful tree mappings:

- `leader-nf`: find in selected directory.
- `leader-ng`: grep in selected directory.
- `leader-yp`: copy relative path.
