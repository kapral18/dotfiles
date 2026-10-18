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

Double-tap **Command** to toggle the Hammerspoon action panel. Type an application
name to launch or focus it, or use one of these explicit search prefixes:

| Input                      | Result                                                          | Enter            |
| -------------------------- | --------------------------------------------------------------- | ---------------- |
| `Safari`                   | Installed applications, exact names before partial matches      | Launch/focus     |
| `tr en спасибо`            | OpenRouter translation into the target language                 | Copy translation |
| `gh repo:owner/name query` | GitHub issues and PRs with repository, number and status        | Open in browser  |
| `emoji woman technologist` | Emoji matched by name, alias and tags                           | Copy Unicode     |
| `sym right arrow`          | Common arrows, keyboard, math, currency and punctuation symbols | Copy Unicode     |
| `ud word or phrase`        | Urban Dictionary suggestions with inline definitions            | Open definition  |

The empty panel lists search commands. Select one to insert its prefix. A keyword
only routes to its provider when followed by a space; otherwise it also searches
apps. Move with **Ctrl-J**/**Ctrl-K**, the arrow keys or **Ctrl-N**/**Ctrl-P**
(selection wraps), press **Enter** to activate, and **Escape** or **Ctrl-C** to
dismiss; clicking elsewhere also dismisses. One Hammerspoon key tap owns these
keys by physical position (they work under any input layout) and consumes them
only while the panel is visible, so other apps never lose them.
The chooser's own key handling does nothing while another app is active (the
usual case after the gesture).
Activating a status-only row dismisses without taking an action. Copy actions do
not paste into the previous app.

Application discovery refreshes on each opening. It scans `/Applications`,
`/System/Applications`, `~/Applications`, CoreServices' Applications folder and
Finder, including nested folders and symlinks without descending into app bundles.
Paths distinguish duplicate names. Matching ignores case and diacritics, including
composed/decomposed Unicode names. It does not depend on Spotlight indexing.

GitHub uses the installed `gh` CLI and its existing authentication (`gh auth login`
if needed); no token belongs in the Hammerspoon config. Queries support GitHub's
`repo:owner/name`, `is:pr`, `is:issue`, and `is:open` filters. The first 30 matches
are shown. Query changes and dismissal terminate pending CLI searches.
Private temporary captures are removed after completion or cancellation; reloading
or quitting Hammerspoon stops outstanding writers and removes their captures too.

Emoji search runs offline against 1,870 entries from
[GitHub gemoji](https://github.com/github/gemoji/tree/fadaeaf1f1a9be82b321316a6c5502e43138b2f6).
The vendored Lua data retains its MIT license. Symbol search is a curated local
set; both support multiple words and copy the exact Unicode sequence. Signed
aliases such as `emoji -1` remain literal. Names and queries share the app search's
Unicode case/diacritic folding.

Translation calls OpenRouter's chat API directly with
`deepseek/deepseek-v4.1-flash-1017`, the model `,q` uses, with reasoning off and no
tools, so the text being translated cannot steer an agent. `tr <target> <text>`
lets the model infer the source; `tr <source>><target> <text>` states it. Only
these codes are offered: `en`, `ru`, `nl`, `es`, `fr`, `hy`, `de`, `it`, `tr`,
`az`, `zh` (Simplified), `zh-Hant` (Traditional), `ja`, `ko`, `la` (Latin), `pt`,
`ar`, `hi`, `uk`, `pl`, `fa` (Persian), `ka` (Georgian), `el` (Greek), `he`, `sv`,
`id`, `vi`; others are rejected without a request. Text is sent to OpenRouter
and its upstream provider.

The API key comes from `pass show openrouter/api/token` on the first translation
and stays only in Hammerspoon's memory until reload; a 401 response drops it so
the next query reads `pass` again. A missing key, network failure, API error or
cut-off reply (`finish_reason` other than `stop`) appears as a non-selectable
row, never as a copyable partial translation. Results from superseded queries
are ignored. If the GPG passphrase is not cached, the first lookup opens
pinentry, which takes focus and closes the panel; reopen it and retry once the
passphrase is entered. In the final native check, all 13 non-English codes and
Armenian/Azerbaijani→English were correct; the first translation (including the
`pass` read) took about 1.6 s, later ones about 0.8 s median. Requests ask
OpenRouter to route by throughput: in 72 measured requests that stayed under
1 s (0.44 s median), while default and latency-sorted routing each produced
~10 s outliers. A typical translation costs about $0.00004.

The gesture accepts either Command key and uses the system double-click interval.
Both presses must be short, with no intervening typing, other modifiers, mouse
clicks or scrolling. Normal Command shortcuts keep propagating and do not open
the panel. Secure Input can prevent macOS from delivering events to Hammerspoon.
`Hyper+U` is no longer bound; existing window-management and `Hyper+R` reload
shortcuts are unchanged. Spotlight keeps its own shortcut and search surface.

The shared chooser in [`readonly_search.lua`](../../../home/dot_hammerspoon/readonly_search.lua)
owns keyword routing, debounce, cancellation, and URL/copy/app activation.
Its `providers` table maps keywords to modules exposing `title`, `hint` and
`search(term, publish, is_current)`. Cheap local lookups set `immediate = true`;
translation retains debounce to avoid a paid request per keystroke.
A search may return a cancellation function. Providers must ignore responses and
avoid follow-up work once `is_current()` is false.
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
chezmoi apply --no-tty --exclude scripts ~/.hammerspoon/{init,search,double_command,urban_dictionary,github,characters,emoji,applications,search_text,translation}.lua
```

## Karabiner

- [`home/dot_config/exact_private_karabiner/karabiner.json`](../../../home/dot_config/exact_private_karabiner/karabiner.json)

Workflow:

- Edit `karabiner.json`.
- Import/reload through Karabiner-Elements.
- Validate by testing the modified key mapping directly.
