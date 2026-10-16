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

### Shared search panel

Double-tap **Command** to toggle the Hammerspoon search panel. It starts empty
and lists the available search keywords. Type `ud <word or phrase>` to search
Urban Dictionary, or select the `ud` entry and press **Enter** to insert its
prefix. Use the arrow keys to select a result; **Enter** opens its definition's
Urban Dictionary webpage in the default browser. **Escape** dismisses the panel.
Activating a status-only row dismisses without opening a page.

The gesture accepts either Command key and uses the system double-click interval.
Both presses must be short, with no intervening typing, other modifiers, mouse
clicks or scrolling. Normal Command shortcuts keep propagating and do not open
the panel. Secure Input can prevent macOS from delivering events to Hammerspoon.
`Hyper+U` is no longer bound; existing window-management and `Hyper+R` reload
shortcuts are unchanged. Spotlight keeps its own shortcut and search surface.

The shared chooser in [`readonly_search.lua`](../../../home/dot_hammerspoon/readonly_search.lua)
owns keyword routing, debounce and cancellation. Its `providers` table maps
keywords to modules exposing `title`, `hint` and `search(term, publish, is_current)`.
Add another search provider there when implementing new functionality. Providers
must ignore responses and avoid follow-up work once `is_current()` is false.
The modifier gesture lives in
[`readonly_double_command.lua`](../../../home/dot_hammerspoon/readonly_double_command.lua).

Urban Dictionary's provider is
[`readonly_urban_dictionary.lua`](../../../home/dot_hammerspoon/readonly_urban_dictionary.lua).
It fetches live autocomplete terms and displays a definition excerpt below each.
It chooses the highest `thumbs_up` among returned matching definitions, keeping
API order for ties, including zero vote counts. It does not fetch additional
definition pages; long text truncates to the native row width. Missing definitions
and network errors appear inline. Late results cannot replace the root panel or
a newer search.

No custom signed app, Apple developer account or additional launcher is needed.
Alfred's package declaration and repository preferences have been removed.

Deploy only the Hammerspoon files, then reload with `Hyper+R` or the app menu:

```sh
chezmoi apply --no-tty --exclude scripts ~/.hammerspoon/{init,search,double_command,urban_dictionary}.lua
```

## Karabiner

- [`home/dot_config/exact_private_karabiner/karabiner.json`](../../../home/dot_config/exact_private_karabiner/karabiner.json)

Workflow:

- Edit `karabiner.json`.
- Import/reload through Karabiner-Elements.
- Validate by testing the modified key mapping directly.
