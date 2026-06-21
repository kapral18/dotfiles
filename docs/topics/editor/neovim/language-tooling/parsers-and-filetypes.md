---
sidebar_position: 1
title: Parsers and filetypes
---

# Parsers and filetypes

## Tree-sitter: bundled parsers and startup hangs

Neovim can load tree-sitter parsers from multiple runtimepath locations. A broken parser under the user site directory can hang startup, especially when the restored session opens a filetype that triggers that parser.

This config prefers Neovim's bundled parser for Markdown:

- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_treesitter.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_treesitter.lua)
- Helper: [`home/dot_config/exact_nvim/exact_lua/exact_util/readonly_treesitter.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_util/readonly_treesitter.lua)

Symptoms:

- `nvim` appears to freeze, often when opening Markdown.
- `nvim --clean` works but regular `nvim` does not.

Local fix:

```bash
ls -la ~/.local/share/nvim/site/parser
rm -f ~/.local/share/nvim/site/parser/markdown.so
```

Parser availability rules:

| Rule                                                 | Reason                                                                                         |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| bundled/runtime parsers count as available           | prevents `nvim-treesitter` from reinstalling languages Neovim already ships                    |
| availability checks `parser/<lang>.*` on runtimepath | `vim.treesitter.language.add()` alone can succeed without a usable parser library              |
| query lookups use `pcall`                            | languages with query files but no parser cache `false` instead of throwing on every `FileType` |

## `*.tmpl` belongs to chezmoi, not Go

`alker0/chezmoi.vim` detects files under `$CHEZMOI_SOURCE_DIR` and sets composite filetypes such as `gitconfig.chezmoitmpl`, `toml.chezmoitmpl`, and `sh.chezmoitmpl`.

`ray-x/go.nvim` ships an eager detector that claims every `.tmpl` file as Go text-template:

```vim
au BufRead,BufNewFile *.tmpl set filetype=gotexttmpl
```

Because plugin `ftdetect/` files are sourced eagerly, that detector can win before go.nvim itself is lazy-loaded. The result can pull in Go syntax and mis-highlight comments with apostrophes.

Defense: [`plugins/chezmoi.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_chezmoi.lua) installs an eager `FileType` autocmd. When a buffer under the chezmoi source tree is set to `gotexttmpl` or `gohtmltmpl`, it restores the composite filetype captured by `chezmoi.vim` or falls back to `chezmoitmpl`.

`readonly_dot_Brewfile.tmpl` is intentionally reclaimed to plain `conf`, not `conf.chezmoitmpl`, because the Brewfile source is managed as configuration text here.
