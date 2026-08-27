#!/usr/bin/env bash
# bg-transform helper behind pick_session's alt-x removal binding.
#
# Owns the two-phase confirmation state so the picker UI never blanks:
#
# CHECK (every invocation start)
#   - Write `${confirm_flag}.run` with this PID. The preflight pause reads as
#     progress through the picker binding's own "removing…" prompt cue, not
#     anything this helper paints; the cue is handed back by whichever action
#     string follows (restore/confirm/hide all end in a prompt change).
#
# NORMAL (no confirm flag)
#   - Snapshot the {+f} selection into `pending_snap`, run
#     `rm_cmd --check` on it (zero-side-effect preflight).
#   - Safe   -> echo SAFE actions: async removal + snapshot-filtered optimistic
#               hide of the checked snapshot from $PICK_SESSION_SORT_SOURCE_FILE,
#               plus prompt/ghost/header restore (the selection may have
#               changed while the check ran; what was checked is what hides).
#   - Blocked -> only if the esc-driven `.run` marker still names this PID:
#               drop the confirm flag and echo CONFIRM actions: prompt/ghost/
#               header swap. Rows stay visible. A second alt-x forces.
#
# CONFIRM (flag present)
#   - Force-dispatch the PENDING snapshot (`--force`) through
#     `dispatch_async.sh`, clear the flag, echo FORCE actions (instant hide +
#     visual restore). Using the stored snapshot means an accidental extra
#     selection toggle cannot widen what gets forced.
#
# Cancel is esc, handled by the picker's shared esc binding, which clears
# every modal flag and this transform's `.run` marker. A blocked check that
# finds its marker deleted mid-flight echoes RESTORE actions so the removing…
# cue hands back to normal visuals without arming confirm mode.
#
# The `.busy` marker makes rapid alt-x presses idempotent while a check is
# in flight instead of racing two transforms into interleaved output.

set -euo pipefail

confirm_flag="${1:-}"
rm_cmd="${2:-}"
sel_in="${3:-}"
pending_snap="${4:-}"

[ -n "$confirm_flag" ] && [ -n "$rm_cmd" ] || exit 0
[ -n "$sel_in" ] && [ -f "$sel_in" ] || exit 0

busy="${confirm_flag}.busy"
run_marker="${confirm_flag}.run"
if [ -e "$busy" ]; then
  exit 0
fi
echo "$$" > "$run_marker"
touch "$busy"
trap 'rm -f "$busy" "$run_marker"' EXIT

dispatch_async_cmd="$(cd "$(dirname "$0")/../lib" && pwd)/dispatch_async.sh"

if [ ! -f "$confirm_flag" ]; then
  _tmp="${pending_snap}.new.$$"
  cp -- "$sel_in" "$_tmp" && mv -f "$_tmp" "$pending_snap"
  if "$rm_cmd" --check "$pending_snap" > /dev/null 2>&1; then
    # Safe: remove now. The dispatched run re-runs its own preflight as an
    # async-race backstop (state changed -> clean abort, no prompt).
    "$dispatch_async_cmd" "$rm_cmd" "$pending_snap" > /dev/null 2>&1 || true
    printf '%s\n' "${ALTX_SAFE_ACTIONS:-}"
  else
    if [ "$(cat "$run_marker" 2> /dev/null)" != "$$" ]; then
      printf '%s\n' "${ALTX_RESTORE_ACTIONS:-}"
      exit 0
    fi
    : > "$confirm_flag"
    printf '%s\n' "${ALTX_CONFIRM_ACTIONS:-}"
  fi
else
  rm -f "$confirm_flag"
  "$dispatch_async_cmd" "$rm_cmd" "$pending_snap" --force > /dev/null 2>&1 || true
  printf '%s\n' "${ALTX_FORCE_ACTIONS:-}"
fi
