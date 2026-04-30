# Terminals

Back: [`docs/categories/index.md`](../index.md)

This repo is designed around a tmux-first workflow, but you still need a solid terminal emulator and a few CLI UX defaults.

## Terminal emulator

Default terminal emulator config:

- [`home/dot_config/exact_ghostty/readonly_config`](../../../home/dot_config/exact_ghostty/readonly_config)

## Bat (better `cat`)

- Config: [`home/dot_config/exact_bat/readonly_config`](../../../home/dot_config/exact_bat/readonly_config)

Themes are pulled via externals into:

- `~/.config/bat/themes`

See [`home/.chezmoiexternal.toml`](../../../home/.chezmoiexternal.toml).

## Yazi (terminal file manager)

- Config: [`home/dot_config/yazi/readonly_yazi.toml`](../../../home/dot_config/yazi/readonly_yazi.toml)
- Theme: [`home/dot_config/yazi/readonly_theme.toml`](../../../home/dot_config/yazi/readonly_theme.toml)
- Installed as: `~/.config/yazi/yazi.toml`

This keeps the config as small override files. Yazi ships its default config internally, so the managed config only records the local preferences: natural sorting, visible dotfiles, size linemode, a larger scrolloff, and wrapped previews.

The theme uses Yazi's flavor system instead of copying a full theme file. Chezmoi installs the Catppuccin Frappe and Latte flavors via [`home/.chezmoiexternal.toml`](../../../home/.chezmoiexternal.toml), then `theme.toml` selects Frappe for dark mode and Latte for light mode.

Tombi reads the inline `$schema` entries in the rendered Yazi TOML files, so TOML LSP hover, completion, and validation work without adding editor-only files to `~/.config/yazi`.

## Next

- Tmux overview + key bindings: [`docs/categories/tmux/index.md`](../tmux/index.md)
