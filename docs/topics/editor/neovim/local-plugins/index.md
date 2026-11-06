---
title: Neovim local plugins
---

# Neovim local plugins

This config ships small in-repo Lua plugins. Loaders live in [`exact_plugins_local/`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/); heavier implementations live in `exact_plugins_local_src/`.

| Slice                                                               | Owns                                                                         |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| [Testing and commit AI](testing-and-commit-ai.md)                   | Jest split runner and Conventional Commit summarizer                         |
| [Ownership, refactors, and panes](ownership-refactors-and-panes.md) | CODEOWNERS lookup/search, TypeScript export moves, send-to-right-pane bridge |
| [Navigation and quickfix](navigation-and-quickfix.md)               | source/test toggle, copy-to-quickfix dirs, quickfix cleanup                  |
| [Window ergonomics](screenshots-and-window-ergonomics.md)           | fit-to-content width toggle, winbar path display                             |

For the rest of the Neovim setup, start at [Editor: Neovim](../index.md).
