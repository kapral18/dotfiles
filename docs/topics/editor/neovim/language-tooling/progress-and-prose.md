---
sidebar_position: 3
title: Progress and prose
---

# Progress and prose

## LSP progress in lualine

Lualine renders native Neovim `LspProgress` events through a local plugin:

- Loader: [`plugins_local/lsp-progress.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_lsp-progress.lua)
- Implementation: [`plugins_local_src/lsp-progress.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_lsp-progress.lua)
- Component wiring: [`plugins/lualine.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_lualine.lua)

The statusline shows client name, spinner, latest title/message, optional server percentage, and a derived completed-token counter such as `(1/1) - done`. It replaces `lsp-progress.nvim` without emitting terminal/tmux OSC progress bars.

## Markdown / MDX prose behavior

Markdown and MDX use Prettier with `--prose-wrap=preserve` so editor formatting does not reflow prose to `printWidth`. For plain Markdown, `unwrap-md` runs after Prettier to unwrap hard-wrapped prose. `unwrap-md` intentionally preserves hard wraps in SOP and managed agent/skill Markdown so AI-facing gates, examples, and exceptions stay visible as separate prompt units.

Relevant files:

- [`plugins/markdown.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_markdown.lua)
- [`core/autocmds.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_autocmds.lua)
- [`util/markdown_view.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_util/readonly_markdown_view.lua)
- [`core/options.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_options.lua)

Session persistence omits `localoptions`, and default Neovim `viewoptions` does not include `options`, so window/buffer options stay driven by config and filetypes rather than replayed session state.
