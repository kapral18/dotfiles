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
