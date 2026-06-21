# macOS Automation

This setup includes macOS-specific automation and preferences. The pieces are separate because some are system defaults, some are app configs, and some are operational hooks.

## Read path

| Slice                                                   | Owns                                                      |
| ------------------------------------------------------- | --------------------------------------------------------- |
| [Defaults and apply flow](defaults-and-apply-flow.md)   | `.osx` scripts, apply workflow, restart expectations      |
| [Hotkeys and launchers](hotkeys-and-launchers.md)       | Hammerspoon, Karabiner, and Alfred backup/reference state |
| [Icons and scheduled jobs](icons-and-scheduled-jobs.md) | custom icon hook, source assets, crontab install          |
| [Verification and troubleshooting](verification.md)     | defaults checks, icon command checks, failure modes       |
| [Apply custom app icons](custom-app-icons.md)           | direct icon command recipe                                |

## Safety note

macOS defaults and key-mapping changes can affect the live desktop. Review with `chezmoi diff`, apply intentionally, and expect some visual changes to require app restart, logout, or reboot.
