---
sidebar_position: 1
title: Defaults and apply flow
---

# Defaults and apply flow

## Defaults / Settings

The raw scripts live here:

- [`home/.osx.core`](../../../home/.osx.core)
- [`home/.osx.extra`](../../../home/.osx.extra)

They are applied via hooks:

- [`home/.chezmoiscripts/run_onchange_after_05-osx.core.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_05-osx.core.sh.tmpl)
- [`home/.chezmoiscripts/run_onchange_after_05-osx.extra.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_05-osx.extra.sh.tmpl)

These scripts can change system behavior. Expect that some changes require a logout/restart to fully take effect.

The current policy keeps quarantine handling and macOS energy management at their
defaults, enables the application firewall without replacing app exceptions, and
uses `StartupMute` for the startup chime. It explicitly selects 24-hour time,
closes windows when quitting apps, and hides internal hard drives on the Desktop.
Applying the core script requires administrator authentication.

Native edge-drag, top-edge and Option-drag tiling, and tiled-window margins are
disabled to preserve the Hammerspoon workflow. Inline predictions remain at the
macOS default; text completion stays enabled.

Finder icon-view settings are merged by `scripts/macos_preferences.py` through
`defaults`, not by editing the live plist file. Missing view dictionaries are
created, unrelated fields are preserved, and failures stop the core apply.
The core hook hashes both the script and this helper, so either change retriggers it.

The extra script configures AppCleaner and quits only AppCleaner, after writing
its preferences. It leaves Alfred and Bartender running.

`AppleFontSmoothing` controls smoothing weight, not removed subpixel rendering.
Undocumented display and animation tweaks are not assumed to work merely because
`defaults read` returns their values.

If you want to disable this category entirely, the most direct approach is to remove or comment out the relevant hook scripts in [`home/.chezmoiscripts/`](../../../home/.chezmoiscripts/).

## Core Apply Workflow

1. Review local dotfiles changes:

```bash
chezmoi diff
```

1. Apply:

```bash
chezmoi apply
```

1. Reboot/log out if settings did not visually update yet.

You can also run `.osx` scripts directly while debugging:

```bash
bash home/.osx.core
bash home/.osx.extra
```
