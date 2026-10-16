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

Check the corrected policy without changing it:

```bash
defaults read -g AppleICUForce24HourTime
defaults read -g NSQuitAlwaysKeepsWindows
defaults read com.apple.finder ShowHardDrivesOnDesktop
defaults read com.apple.WindowManager EnableTilingByEdgeDrag
defaults read com.apple.WindowManager EnableTopTilingByEdgeDrag
defaults read com.apple.WindowManager EnableTilingOptionAccelerator
defaults read com.apple.WindowManager EnableTiledWindowMargins
nvram StartupMute
/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
```

Expect `1` for 24-hour time, `0` for window restoration, drive visibility and
tiling, `%01` for startup mute, and an enabled firewall.
`LSQuarantine` in `com.apple.LaunchServices`, the global `NSAppSleepDisabled` and
`NSDisableAutomaticTermination`, and Finder's old
`ShowSidebarHardDrivesOnDesktop` override should be absent.
System Settings should inherit the global window-restoration preference, without
its old `NSQuitAlwaysKeepsWindows` override.

Run the isolated Finder regression suite with:

```bash
python3 scripts/test_runner.py tests/test_macos_preferences.py
```

On macOS, these tests use the real `defaults` binary with absolute domains under
temporary directories, never your Finder domain. They cover missing dictionaries,
preserving unrelated preferences, reapplying after user changes, and malformed
data without partial writes. Other platforms skip these native-consumer tests.
Stored values are not proof of an undocumented setting's UI effect; check the
affected app after relaunch when verifying that behavior.

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
