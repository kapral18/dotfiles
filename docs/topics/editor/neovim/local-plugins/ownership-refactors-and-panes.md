---
sidebar_position: 2
title: Ownership, refactors, and panes
---

# Ownership, refactors, and panes

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

1. The attached `typescript-tools` client requests TypeScript's native **Move to file** refactor for the selected lines.
2. TypeScript returns one workspace edit for the declarations, their import dependencies, importers, and any required `tsconfig.json` file list changes.
3. The editor applies those edits to buffers. Existing target content remains; a modified target must be saved first. If applying the edit fails, the affected buffer contents and modified flags are restored.
4. Review the affected buffers and save them. The command leaves files unsaved; the configured `BufWritePre` hook creates missing parent directories when you save.

The selection must contain statements that TypeScript can move. An unavailable refactor, rejected target, or buffer change during the request leaves the refactor unapplied. The command needs `pmizio/typescript-tools.nvim` attached and a TypeScript version that supports the interactive **Move to file** refactor. See [TypeScript tools](../language-tooling/lsp-and-source-jumps.md#typescript-tools).

## Pane bridge: send text to the right pane (local plugin)

If you run a REPL, test watcher, or agent in the herdr pane to the right, you can send data from Neovim to it. The text arrives as one bracketed paste, so an agent prompt takes it without submitting line by line.

- `leader-ad` send diagnostics
- `leader-al` send current line
- `leader-av` send selection
- `leader-ah` send git hunk
- `leader-ag` send git diff (file)

Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_send-to-right-pane.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_send-to-right-pane.lua)
