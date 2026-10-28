---
sidebar_position: 3
---

# Terminals

This repo is designed around a tmux-first workflow, but you still need a solid terminal emulator and a few CLI UX defaults.

## Terminal emulator

Default terminal emulator config:

- [`home/dot_config/exact_ghostty/readonly_config`](../../../home/dot_config/exact_ghostty/readonly_config)

### Ghostty 1.4

Native Ghostty shells enable `ssh-env` and `ssh-terminfo`. Running `ssh` uses Ghostty's `+ssh` integration to install its bundled terminfo on the remote host and forward terminal environment variables. Successful installs are cached per host and port; failed installs fall back to `xterm-256color`. Environment forwarding depends on the remote server's `AcceptEnv` settings.

Tmux panes keep their own `xterm-256color` identity and ordinary `ssh`. Ghostty's native shell integration is injected into the shell it launches, not every shell inside tmux. Do not alias `ssh` globally to `ghostty +ssh`: that wrapper selects `xterm-ghostty`, which describes Ghostty rather than tmux.

These 1.4 improvements work through the defaults:

- Compressed scrollback with a 50 MB limit per Ghostty terminal. Tmux's separate 10,000-line history stays unchanged.
- Kitty graphics animation and relative placements, plus faster image handling. Tmux already enables passthrough; applications still need to support it.
- Kitty clipboard support for images and other formats. Reads and writes follow the existing `clipboard-read` and `clipboard-write` settings.

The explicit `copy-on-select = clipboard` still copies selections to the system clipboard on macOS. `Cmd+Up` and `Cmd+Down` jump between native shell prompts; `Cmd+Home` and `Cmd+End` scroll to the ends of the history. Configuration help is available with `ghostty +explain-config <key>`.

See the [Ghostty 1.4.0 release notes](https://ghostty.org/docs/install/release-notes/1-4-0).

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

## Git TUIs

Two terminal git clients are configured; pick whichever fits the task (the [git identity](git-identity/index.md) and [git skill](../ai-assistants/index.md) cover the underlying workflow):

- lazygit — [`home/dot_config/exact_lazygit/config.yml`](../../../home/dot_config/exact_lazygit/config.yml)
- tig — [`home/dot_config/exact_tig/readonly_config`](../../../home/dot_config/exact_tig/readonly_config)

A PR-focused dashboard, gh-dash, is configured separately under [`home/dot_config/exact_gh-dash/`](../../../home/dot_config/exact_gh-dash/) (one config plus shared settings).

## System monitor (btop)

- Config: [`home/dot_config/exact_btop/btop.conf`](../../../home/dot_config/exact_btop/btop.conf)

## Next

- [Tmux overview + key bindings](tmux/index.md)
