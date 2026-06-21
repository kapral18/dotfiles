---
sidebar_position: 4
title: Verification and troubleshooting
---

# Verification and troubleshooting

## Verification

Check a few high-signal defaults:

```bash
defaults read -g KeyRepeat
defaults read com.apple.screencapture location
defaults read net.freemacsoft.AppCleaner SUAutomaticallyUpdate
```

Check icon command wiring:

```bash
command -v ,apply-app-icons
```

## Troubleshooting

- `defaults` changes did not apply:
  - restart affected apps (`Finder`, `Dock`, `SystemUIServer`) or reboot.
- `,apply-app-icons` fails:
  - verify `fileicon` and `yq` are installed.
  - verify [`home/app_icons/readonly_icon_mapping.yaml`](../../../home/app_icons/readonly_icon_mapping.yaml) and asset files exist.
- Hook runs but nothing changed:
  - confirm the script hash-trigger input actually changed.

## Related

- [Apply custom app icons](custom-app-icons.md)
- [New machine bootstrap](../../intro/new-machine-bootstrap.md)
- [Debugging hooks](../core/chezmoi/debug-hooks.md)
