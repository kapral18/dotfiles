---
sidebar_position: 4
title: Screenshots and window ergonomics
---

# Screenshots and window ergonomics

## Code Screenshots (Local Plugin): `freeze`

Generate an image of code directly from Neovim using the `freeze` CLI.

- Homebrew formula (already managed by this repo's Brewfile): `brew "charmbracelet/tap/freeze"` in [`home/readonly_dot_Brewfile.tmpl`](../../../../../home/readonly_dot_Brewfile.tmpl)
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_freeze.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_freeze.lua)
- Source: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_freeze.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_freeze.lua)

Commands:

- `:Freeze` - capture the whole buffer (or a range, e.g. `:10,40Freeze`)
- `:FreezeLine` - capture the current line

Behavior:

- Writes `~/Downloads/screenshots/freeze.png`
- Copies the PNG to clipboard (macOS) and opens the image after generation

## Toggle Window Width (Local Plugin)

Toggles the current window width between the previous value and a "fit to content" width.

- Keymap: `leader-=`
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_toggle-win-width.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_toggle-win-width.lua)

## Winbar: Show Remainder Path (Local Plugin)

This config sets a custom winbar that shows the remainder of the current path in a compact way.

- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_winbar.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_winbar.lua)
