#!/bin/bash
set -euo pipefail

if defaults write com.apple.universalaccess chezmoiAccessProbe -bool true 2> /dev/null; then
  defaults delete com.apple.universalaccess chezmoiAccessProbe
  exit 0
fi
open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
cat << 'MSG' >&2
This terminal cannot change protected macOS settings yet. In System Settings > Privacy & Security > Full Disk Access,
allow this terminal app, then quit and reopen the terminal and rerun the command.
MSG
exit 1
