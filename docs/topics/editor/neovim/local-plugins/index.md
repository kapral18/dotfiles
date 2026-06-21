---
title: Neovim local plugins
---

# Neovim local plugins

This config ships small in-repo Lua plugins. Loaders live in [`exact_plugins_local/`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/); heavier implementations live in `exact_plugins_local_src/`.

| Slice                                                                     | Owns                                                                                |
| ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| [Testing and commit AI](testing-and-commit-ai.md)                         | Jest split runner and Conventional Commit summarizer                                |
| [Ownership, refactors, and tmux](ownership-refactors-and-tmux.md)         | CODEOWNERS lookup/search, TypeScript export moves, send-to-right-pane bridge        |
| [Navigation and quickfix](navigation-and-quickfix.md)                     | source/test toggle, ESLint reference jumps, copy-to-quickfix dirs, quickfix cleanup |
| [Screenshots and window ergonomics](screenshots-and-window-ergonomics.md) | `freeze`, fit-to-content width toggle, winbar path display                          |

For the rest of the Neovim setup, start at [Editor: Neovim](../index.md).
