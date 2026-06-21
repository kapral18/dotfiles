---
sidebar_position: 2
title: Ownership, refactors, and tmux
---

# Ownership, refactors, and tmux

## Ownership / CODEOWNERS Workflows (Local Plugins)

Show owner of the current file:

- Keymap: `leader-0`
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_show-file-owner.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_show-file-owner.lua)

Search only paths owned by a team/owner:

- Keymaps: `leader-rg`, `leader-rG`, `leader-fd`, `leader-fD`
- Commands: `:OwnerCodeGrep`, `:OwnerCodeFd`, `:ListOwners`
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_owner-code-search.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_owner-code-search.lua)

## Refactors: Move TS Exports (Local Plugin)

Select one or more exported declarations in visual mode, enter a target path (relative to the current file), and the plugin moves the selection into that file and re-wires every importer to point at the new location.

- Visual mode mapping: `leader-]`
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_ts-move-exports.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_ts-move-exports.lua)
- Source: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_ts-move-exports.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_ts-move-exports.lua)

How it works:

1. Treesitter collects the exported binding names in the selection (`const`/`function`/`class`/`type`).
2. `textDocument/references` records every file that imports them.
3. Each export is renamed to a temporary placeholder, then the lines are moved into the target file (parent dirs are created; appended after a blank line if the file already exists).
4. Each referencing file is opened, and `typescript-tools`' add-missing-imports re-imports the placeholder from the new file.
5. The placeholder is renamed back to the original name from the new file; the LSP rename propagates the original name through every importer.

Requirements:

- Depends on the `typescript-tools` LSP client (`pmizio/typescript-tools.nvim`) being attached — it drives references, rename, and add-missing-imports. See [Editor: Neovim](../index.md) for the TypeScript LSP setup.

## tmux Bridge: Send Text To The Right Pane (Local Plugin)

If you run a REPL/test watcher in tmux, you can send data from Neovim to the pane to the right.

- `leader-ad` send diagnostics
- `leader-al` send current line
- `leader-av` send selection
- `leader-ah` send git hunk
- `leader-ag` send git diff (file)

Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_send-to-tmux-right-pane.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_send-to-tmux-right-pane.lua)
