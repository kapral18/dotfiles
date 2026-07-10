---
sidebar_position: 3
title: Navigation and quickfix
---

# Navigation and quickfix

## Jump Between Source And Test Files (Local Plugin)

If you keep `foo.ts` and `foo.test.ts` (or `.spec`, `_test`, etc) side-by-side, this mapping toggles between them.

- Keymap: `Ctrl-^`
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_switch-src-test.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_switch-src-test.lua)
- Source: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_switch-src-test.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_switch-src-test.lua)

It supports extension fallbacks (ts <-> tsx <-> js <-> jsx) when the exact match does not exist.

## Copy Current Buffer To Quickfix Directories (Local Plugin)

If your quickfix list includes matches across multiple directories, this helper can copy the current file into each of those directories (useful for applying a file-based fix across multiple worktrees/sandboxes).

- Keymap: `leader-cb` (copy)
- Keymap: `leader-cB` (copy forced)
- Command: `:CopyBufferToQfDirs` (optional `force`)
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_copy-to-qf.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_copy-to-qf.lua)

## Quickfix Ergonomics (Local Plugin)

Quickfix is treated as a first-class workflow. Add-ons:

- `:QFDedupe` dedupe entries
- `leader-rqi` filter include pattern
- `leader-rqx` filter exclude pattern
- inside quickfix window: `dd` removes an entry

Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_qf.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_qf.lua)
