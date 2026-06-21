---
title: Neovim PackDashboard
---

# Neovim PackDashboard

The Neovim config uses built-in `vim.pack` with a custom dashboard layered on top. The dashboard is the review surface for plugin status, drift, risky pins, pending updates, and orphan cleanup.

![Neovim PackDashboard floating inside the editor pane while the rest of the tmux layout remains visible](../../assets/neovim-pack-dashboard-inline.png)

Open it with:

```vim
:PackDashboard
```

Raw reports are still available with `:PackSync` and `:PackStatus`.

| Slice                                                       | Owns                                                             |
| ----------------------------------------------------------- | ---------------------------------------------------------------- |
| [Loading and version policy](loading-and-version-policy.md) | lazy-style specs, trigger-aware loading, tag-vs-branch heuristic |
| [Dashboard UI](dashboard-ui.md)                             | row signals, selection, details popup, compare/repo shortcuts    |
| [Operations and commands](operations-and-commands.md)       | refresh/update/clean behavior, tuning globals, command surface   |
