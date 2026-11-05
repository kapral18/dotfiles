#!/usr/bin/env bash
# Body of the herdr picker popups (prefix+T: session, prefix+G: github).
# alt-g in either picker leaves a sentinel in this loop's handoff namespace;
# the loop then runs the other picker in the same popup.
set -euo pipefail

pickers="$HOME/.config/herdr/scripts/pickers"
handoff="$pickers/lib/handoff_namespace.py"

entry=session-popup
[ "${1:-session}" != github ] || entry=gh-popup
token="$("$handoff" begin --owner-pid "$$" --owner-role popup-loop --entry "$entry")" || {
  herdr notification show picker --body "picker handoff: unavailable" > /dev/null 2>&1 || true
  exit 1
}
export PICKER_HANDOFF_TOKEN="$token"
trap '"$handoff" end --owner-pid "$$" --token "$PICKER_HANDOFF_TOKEN" > /dev/null 2>&1 || true' EXIT
trap 'exit 0' INT HUP TERM

to_gh="$("$handoff" path pick_session_switch_gh)"
to_sessions="$("$handoff" path gh_picker_switch_sessions)"

next="${1:-session}"
while true; do
  case "$next" in
    session)
      bash "$pickers/session/pick_session.sh" || true
      [ -f "$to_gh" ] || break
      rm -f "$to_gh"
      next=github
      ;;
    github)
      bash "$pickers/github/gh_picker.sh" || true
      [ -f "$to_sessions" ] || break
      rm -f "$to_sessions"
      next=session
      ;;
    *) exit 2 ;;
  esac
done
