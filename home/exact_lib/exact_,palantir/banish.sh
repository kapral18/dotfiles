#!/usr/bin/env bash
# ,palantir banish <id> [--force] — fail-closed legion teardown. Refuses when
# the legion is mid-flight (any stage other than cleared_for_human/holding/
# banished) or the worktree is dirty, unless --force. Closing routes the
# memory packet through the machine before the session dies.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tmux_lib.sh
. "$SCRIPT_DIR/tmux_lib.sh"

LEGION_STATE_PY="$SCRIPT_DIR/legion_state.py"
SUPERVISOR_PY="$SCRIPT_DIR/supervisor.py"

legion_id=""
force=0
preflight=0
teardown_only=0
teardown_started=0

record_teardown_failure() {
  if [ "$teardown_started" = 1 ] && [ -n "$legion_id" ]; then
    python3 "$LEGION_STATE_PY" set "$legion_id" teardown_status failed > /dev/null 2>&1 || true
  fi
}
trap record_teardown_failure ERR

while [ $# -gt 0 ]; do
  case "$1" in
    --force)
      force=1
      shift
      ;;
    --preflight)
      preflight=1
      shift
      ;;
    --teardown-only)
      teardown_only=1
      shift
      ;;
    *)
      legion_id="$1"
      shift
      ;;
  esac
done

if [ -z "$legion_id" ]; then
  echo "usage: ,palantir banish <id> [--force]" >&2
  exit 1
fi

# Lock-only debris dir (no manifest): fail-closed removal, full-banish mode only.
if [ "$preflight" = 0 ] && [ "$teardown_only" = 0 ]; then
  manifest_path="$(python3 "$LEGION_STATE_PY" paths "$legion_id" | python3 -c 'import sys,json; print(json.load(sys.stdin)["manifest"])')"
  if [ -d "$(dirname "$manifest_path")" ] && [ ! -f "$manifest_path" ]; then
    exec python3 "$LEGION_STATE_PY" remove-debris "$legion_id"
  fi
fi

manifest="$(python3 "$LEGION_STATE_PY" show "$legion_id")"
stage="$(printf '%s' "$manifest" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("stage",""))')"
worktree="$(printf '%s' "$manifest" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("worktree",""))')"
session="$(printf '%s' "$manifest" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("session",""))')"
git_root="$(printf '%s' "$manifest" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("git_root",""))')"
owns_worktree="$(printf '%s' "$manifest" | python3 -c 'import sys,json; print(str(bool(json.load(sys.stdin).get("owns_worktree"))).lower())')"

if [ "$force" != 1 ]; then
  case "$stage" in
    cleared_for_human | holding | banished) ;;
    *)
      echo "Error: legion $legion_id is in-flight (stage=$stage); resolve it or use --force" >&2
      exit 1
      ;;
  esac
  if [ "$owns_worktree" = "true" ] && [ -n "$worktree" ] && [ -d "$worktree" ]; then
    if ! worktree_status="$(git -C "$worktree" status --porcelain=v1 2>&1)"; then
      echo "Error: cannot verify legion worktree cleanliness: $worktree" >&2
      echo "$worktree_status" >&2
      exit 1
    fi
    if [ -n "$worktree_status" ]; then
      echo "Error: legion worktree is dirty: $worktree; land or stash it, or use --force" >&2
      exit 1
    fi
  fi
fi

if [ "$preflight" = 1 ]; then
  exit 0
fi

if [ "$teardown_only" != 1 ] && [ "$stage" != "banished" ]; then
  python3 "$SUPERVISOR_PY" dispatch "$legion_id" --json-event '{"kind":"banish"}' > /dev/null
fi
teardown_started=1
python3 "$LEGION_STATE_PY" set "$legion_id" teardown_status running
python3 "$SUPERVISOR_PY" stop "$legion_id" > /dev/null 2>&1 || true
python3 "$SUPERVISOR_PY" run "$legion_id" --once > /dev/null
if [ -n "$session" ]; then
  _palantir_kill_session "$session"
fi
if [ "$owns_worktree" = "true" ] && [ -d "$worktree" ]; then
  branch="$(git -C "$worktree" branch --show-current 2> /dev/null || true)"
  if [ "$force" = 1 ]; then
    git -C "$git_root" worktree remove --force "$worktree"
  else
    git -C "$git_root" worktree remove "$worktree"
  fi
  if [ -n "$branch" ]; then
    if [ "$force" = 1 ]; then
      git -C "$git_root" branch -D "$branch" > /dev/null
    elif ! git -C "$git_root" branch -d "$branch" > /dev/null 2>&1; then
      echo "Warning: preserved unmerged legion branch '$branch'" >&2
    fi
  fi
fi
python3 "$LEGION_STATE_PY" set "$legion_id" teardown_status complete
trap - ERR
if [ "$teardown_only" = 1 ]; then
  echo "legion $legion_id granted and torn down"
else
  echo "legion $legion_id banished"
fi
