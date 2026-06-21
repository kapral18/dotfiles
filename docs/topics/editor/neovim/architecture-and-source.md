---
sidebar_position: 1
title: Architecture and source
---

# Architecture and source

## Where the config lives

| Surface                      | Path                                                                                                             |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Source                       | [`home/dot_config/exact_nvim/`](../../../../home/dot_config/exact_nvim)                                          |
| Installed target             | `~/.config/nvim/`                                                                                                |
| Core                         | [`exact_lua/exact_core/`](../../../../home/dot_config/exact_nvim/exact_lua/exact_core)                           |
| Plugin specs                 | [`exact_lua/exact_plugins/`](../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins)                     |
| Local plugin loaders         | [`exact_lua/exact_plugins_local/`](../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local)         |
| Local plugin implementations | [`exact_lua/exact_plugins_local_src/`](../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src) |

Chezmoi source paths use prefixes such as `exact_`; installed paths do not. For example:

```text
home/dot_config/exact_nvim/exact_lua/ -> ~/.config/nvim/lua/
home/dot_config/exact_nvim/exact_after/ -> ~/.config/nvim/after/
```

Leader keys:

- `mapleader` is space.
- `maplocalleader` is `\`.

Neovim itself is version-managed by mise:

- [`home/dot_config/mise/config.toml.tmpl`](../../../../home/dot_config/mise/config.toml.tmpl) (`neovim = "0.12.2"`)

## Quick start

1. Install the pinned Neovim version:

   ```bash
   mise install neovim@0.12.2
   ```

2. Apply dotfiles:

   ```bash
   chezmoi apply
   ```

3. Launch Neovim:

   ```bash
   nvim
   ```

4. Open the plugin dashboard:

   ```vim
   :PackDashboard
   ```

![Neovim PackDashboard floating inside the editor pane while the rest of the tmux layout remains visible](../assets/neovim-pack-dashboard-inline.png)

## Customization entry points

| Change          | Start here                                                                                               |
| --------------- | -------------------------------------------------------------------------------------------------------- |
| Options         | [`core/options.lua`](../../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_options.lua)   |
| Keymaps         | [`core/keymaps.lua`](../../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_keymaps.lua)   |
| Autocmds        | [`core/autocmds.lua`](../../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_autocmds.lua) |
| Plugin config   | [`plugins/`](../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins)                             |
| Local workflows | [`plugins_local_src/`](../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src)         |

`core/` is foundational editor behavior. `plugins/` is plugin configuration grouped by topic/language. `plugins_local_src/` contains workflow-specific Lua plugins written in this repo.
