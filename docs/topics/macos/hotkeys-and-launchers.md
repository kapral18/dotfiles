---
sidebar_position: 2
title: Hotkeys and launchers
---

# Hotkeys and launchers

## Hammerspoon

- Config: [`home/dot_hammerspoon/readonly_init.lua`](../../../home/dot_hammerspoon/readonly_init.lua)

Key pieces:

- Window management hotkeys: [`home/dot_hammerspoon/readonly_window.lua`](../../../home/dot_hammerspoon/readonly_window.lua)
- Grid-mouse (keyboard mouse): [`home/dot_hammerspoon/readonly_gridmouse.lua`](../../../home/dot_hammerspoon/readonly_gridmouse.lua) (currently not enabled in `init.lua`)

In `init.lua`, `Hyper` is configured as `ctrl+alt+cmd`.

This setup pulls the `EmmyLua.spoon` via externals:

- [`home/.chezmoiexternal.toml`](../../../home/.chezmoiexternal.toml)

Workflow:

- Edit modules under [`home/dot_hammerspoon/`](../../../home/dot_hammerspoon/).
- Reload Hammerspoon config from the app menu.
- Verify configured keybindings in `init.lua` and module files.

## Karabiner

- [`home/dot_config/exact_private_karabiner/karabiner.json`](../../../home/dot_config/exact_private_karabiner/karabiner.json)

Workflow:

- Edit `karabiner.json`.
- Import/reload through Karabiner-Elements.
- Validate by testing the modified key mapping directly.

## Alfred

- [`home/Alfred.alfredpreferences/`](../../../home/Alfred.alfredpreferences/)

Note: this directory is currently ignored by `chezmoi` via [`home/.chezmoiignore`](../../../home/.chezmoiignore). It is kept in the repo as a reference/backup rather than being automatically installed.
