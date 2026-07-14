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
while [ $# -gt 0 ]; do
  case "$1" in
    --force)
      force=1
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
  if [ -n "$worktree" ] && [ -d "$worktree" ] \
    && [ -n "$(git -C "$worktree" status --porcelain=v1 2> /dev/null | head -1)" ]; then
    echo "Error: legion worktree is dirty: $worktree; land or stash it, or use --force" >&2
    exit 1
  fi
fi

if [ "$stage" != "banished" ]; then
  python3 "$SUPERVISOR_PY" dispatch "$legion_id" --json-event '{"kind":"banish"}' > /dev/null
fi
python3 "$SUPERVISOR_PY" stop "$legion_id" > /dev/null 2>&1 || true
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
echo "legion $legion_id banished"
