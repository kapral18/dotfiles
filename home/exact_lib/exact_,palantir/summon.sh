#!/usr/bin/env bash
# ,palantir summon <goal> — summon a legion: allocate a disposable ,w worktree,
# create the legion tmux session (window 0 = command: coordinator agent pane +
# supervisor pane), register the manifest, and start the deterministic
# supervisor. The supervisor starts triage on its first tick; role stages get
# their own windows as the machine reaches them.
#
# Shell glue only: sources tmux_lib.sh + worktree_lib.sh, calls git/tmux and
# the Python cores. All decisions live in machine.py/legion_state.py.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tmux_lib.sh
. "$SCRIPT_DIR/tmux_lib.sh"
# shellcheck source=../shared/worktree_lib.sh
. "$SCRIPT_DIR/../shared/worktree_lib.sh"
# shellcheck source=../shared/bash_utils_lib.sh
. "$SCRIPT_DIR/../shared/bash_utils_lib.sh"

LEGION_STATE_PY="$SCRIPT_DIR/legion_state.py"
CONFIG_PY="$SCRIPT_DIR/palantir_config.py"

usage() {
  cat << EOF
Usage: ,palantir summon [options] <goal>

Raise a legion: an autonomous effort in its own tmux session on a disposable
,w worktree, with a coordinator agent pane and a deterministic supervisor.

Options:
  --base <ref>          base ref for the worktree (default: repo default branch)
  --criteria <json>     acceptance criteria JSON: [{"text": "...", "check": "..."}]
  --no-worktree         run in the current directory instead of a new worktree
  -h, --help            show this help

The goal is free text. Quote multi-word goals.
EOF
}

base=""
criteria="[]"
use_worktree=1
goal=""

while [ $# -gt 0 ]; do
  case "$1" in
    -h | --help)
      usage
      exit 0
      ;;
    --base)
      base="${2:?--base needs a ref}"
      shift 2
      ;;
    --criteria)
      criteria="${2:?--criteria needs JSON}"
      shift 2
      ;;
    --no-worktree)
      use_worktree=0
      shift
      ;;
    *)
      goal="$1"
      shift
      ;;
  esac
done

if [ -z "$goal" ]; then
  usage >&2
  exit 1
fi

git_root="$(git rev-parse --show-toplevel 2> /dev/null || true)"
if [ -z "$git_root" ]; then
  echo "Error: ,palantir summon must run inside a git repository" >&2
  exit 1
fi

# --- resolve roles + validate criteria BEFORE allocating anything ----------- #
# The diversity guard and a criteria JSON typo must fail here, not after a
# worktree/branch has been created.
roles_json="$(python3 "$CONFIG_PY" roles)"
if ! python3 -c '
import json, sys
sys.path.insert(0, sys.argv[2])
import machine
try:
    machine.resolve_roles(json.loads(sys.argv[1]))
except machine.MachineError as exc:
    print(f"Error: {exc}", file=sys.stderr)
    raise SystemExit(1)
' "$roles_json" "$SCRIPT_DIR"; then
  exit 1
fi
if ! python3 -c 'import json,sys; json.loads(sys.argv[1])' "$criteria" 2> /dev/null; then
  echo "Error: --criteria is not valid JSON" >&2
  exit 1
fi
max_attempts="$(python3 "$CONFIG_PY" get max_implement_attempts)"

# --- allocate the worktree (mirror ,w add's local-branch path) -------------- #
worktree="$git_root"
if [ "$use_worktree" = 1 ]; then
  legion_slug="$(python3 -c 'import uuid; print("l" + uuid.uuid4().hex[:6])')"
  branch="legion-${legion_slug}"
  parent_dir="$(_get_worktree_parent_dir)"
  worktree="${parent_dir}/${branch}"
  if [ -z "$base" ]; then
    base="$(_comma_w_detect_default_branch)"
  fi
  if [ -z "$base" ]; then
    echo "Error: could not detect a default branch; pass --base <ref>" >&2
    exit 1
  fi
  if [ -e "$worktree" ]; then
    echo "Error: worktree path already exists: $worktree" >&2
    exit 1
  fi
  if ! git worktree add "$worktree" -b "$branch" "$base" > /dev/null 2>&1; then
    echo "Error: git worktree add failed (base=$base branch=$branch)" >&2
    exit 1
  fi
fi

# --- register the legion ----------------------------------------------------- #
legion_id="$(python3 "$LEGION_STATE_PY" new --goal "$goal" --git-root "$git_root" \
  --worktree "$worktree" --roles "$roles_json" --criteria "$criteria" \
  --max-implement-attempts "$max_attempts")"
session="$(_palantir_session_name "$legion_id")"
python3 "$LEGION_STATE_PY" set "$legion_id" session "$session"

# --- create the legion session ----------------------------------------------- #
if ! _palantir_spawn_session "$session" "$worktree"; then
  echo "Error: could not create tmux session '$session' (is tmux running?)" >&2
  exit 1
fi

# --- supervisor pane in window 0 (right split; coordinator owns pane 0) ------ #
_palantir_tmux split-window -d -h -t "=${session}:command" -c "$worktree" \
  "python3 $(_palantir_sh_quote "$SCRIPT_DIR/supervisor.py") run $(_palantir_sh_quote "$legion_id")" 2> /dev/null || true

echo "legion $legion_id summoned: session=$session worktree=$worktree"
echo "attach: tmux switch-client -t '$session'   stone: ,palantir"
