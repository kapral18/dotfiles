---
sidebar_position: 2
title: LSP and source jumps
---

# LSP and source jumps

## LSP code actions

`<leader>ca` and `<leader>cA` show code actions with `fzf-lua`, not Neovim's default `vim.ui.select`.

`fzf-lua` is key-triggered and registers `vim.ui.select` globally only after first load, so these mappings call `fzf-lua`'s `lsp_code_actions` helper directly. That keeps the code-action picker consistent even early in a session.

## Rust analyzer

[`plugins/rust.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_rust.lua) configures rustaceanvim with:

- `cargo.allFeatures = true`
- `check.command = "clippy"`
- `checkOnSave = true`

Rustaceanvim is the only rust-analyzer client. [`plugins/lsp.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_lsp.lua) excludes the generic `nvim-lspconfig` `rust_analyzer` server from Mason-lspconfig auto-enable while Mason still installs the binary. That avoids duplicate definition/reference rows from two clients.

## Lua LS workspace scope

`lua_ls` root detection is narrowed for chezmoi paths. A file under the chezmoi source tree uses its own directory as the workspace root instead of the repo `.git` root, avoiding full-tree scans and the "More than 100000 files have been scanned" warning.

Root resolution priority in [`plugins/lua.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_lua.lua):

1. Real lua_ls project markers: `.luarc.json` / `.luarc.jsonc`.
2. Chezmoi source-tree file directory.
3. Formatter/linter markers such as `.stylua.toml`, `stylua.toml`, `selene.toml`.
4. `.git`.

The chezmoi check must precede formatter markers because `.stylua.toml` lives at the chezmoi repo root.

Two Neovim 0.11+ details matter:

- Native LSP `root_dir` signature is `fun(bufnr, on_dir)`: the chosen root is passed to `on_dir`, not returned.
- lazydev's lspconfig integration is disabled so it does not override `root_dir` with `.git` root detection. Its library/annotation injection still works.

## Jump to source, not target

When editing chezmoi source files, language servers often resolve symbols against deployed copies under `$HOME`. A plain `gd` or `gr` from `home/dot_config/exact_nvim/...` could jump to `~/.config/nvim/...`, which `chezmoi apply` overwrites.

[`util/chezmoi_lsp.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_util/readonly_chezmoi_lsp.lua) wraps `vim.lsp.buf_request{,_sync}` and rewrites location results so managed targets map back to their source path via `chezmoi source-path`.

Scope:

- only when the originating buffer is a chezmoi source file.
- only location methods: definition, declaration, type definition, implementation, references.
- hover, formatting, and code actions pass through untouched.
- plugin/runtime paths are skipped before any `chezmoi` probe.
- resolutions, including misses, are cached.

Line/column are preserved. For templates, rows may drift but the source file is still correct.
