---
title: "Editor: Neovim"
---

# Editor: Neovim

Neovim is the inline editor pane in the tmux workbench. Pickers and dashboards appear around it; editor-specific UI, such as `:PackDashboard`, stays inside Neovim.

## Read path

| Slice                                                 | Owns                                                                                     |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| [Architecture and source](architecture-and-source.md) | source layout, installed target, quick start, customization entry points                 |
| [PackDashboard](pack-dashboard/index.md)              | built-in `vim.pack`, version policy, risk/drift/orphan UI, operations                    |
| [Language tooling](language-tooling/index.md)         | tree-sitter, filetypes, LSP setup, chezmoi source jumps, prose formatting                |
| [Workflows](workflows/index.md)                       | keymaps, search, git, local plugin entrypoints, IDE translation                          |
| [Local plugins](local-plugins/index.md)               | in-repo Lua plugins for tests, git AI, ownership, refactors, tmux, quickfix, screenshots |

## What you get

- Keyboard-first editing with discoverable keymaps.
- Fast repo search through fzf-lua.
- Tight JS/TS test loops in editor splits.
- Git hunk, history, and diff ergonomics.
- Local plugins for daily repo workflows.
- Project-aware formatting: Oxfmt when declared, else Biome, else Prettier.
- ESLint and Oxlint diagnostics together, with a single formatter to avoid conflicts.

## Related

- [Terminals](../../workflow/terminals.md)
- [Tmux](../../workflow/tmux/index.md)
