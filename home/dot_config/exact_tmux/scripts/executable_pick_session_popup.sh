#!/usr/bin/env bash
set -euo pipefail

IFS='|' read -r height width orig_shell < <(
  tmux display-message -p \
    '#{@pick_session_popup_height}|#{@pick_session_popup_width}|#{default-shell}' \
    2>/dev/null || true
)
[ -n "${height:-}" ] || height="40"
[ -n "${width:-}" ] || width="80"
[ -n "${orig_shell:-}" ] || orig_shell="/bin/sh"

# Swap default-shell to /bin/sh for the popup so heavy shells (fish, zsh with
# plugins) don't add ~1 s of startup overhead.  The three tmux commands execute
# atomically in the server's command queue, so the restore fires as soon as the
# popup process is spawned.
tmux set-option -g default-shell /bin/sh \; \
  display-popup -E -h "${height}%" -w "${width}%" -d "#{pane_current_path}" \
  "$HOME/.config/tmux/scripts/pick_session.sh" \; \
  set-option -g default-shell "$orig_shell" 2>/dev/null || true
