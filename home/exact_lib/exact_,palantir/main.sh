#!/usr/bin/env bash
# ,palantir — legion orchestration through the seeing stone. Thin dispatcher;
# internals live in sibling Python cores (machine.py, legion_state.py,
# supervisor.py, panes.py, composer.py) and summon.sh/banish.sh shell glue.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

require_human_control() {
  local action="$1"
  if [ -n "${PALANTIR_AGENT_ROLE:-}" ]; then
    echo "Error: ,palantir $action is human-only (agent role: $PALANTIR_AGENT_ROLE)" >&2
    exit 1
  fi
}

show_usage() {
  cat << EOF
Usage: ,palantir [command] [options]

Legions (1 legion = 1 effort = 1 tmux session; windows/panes are its organisation):
  summon <goal>            Summon a legion: worktree + tmux session + coordinator + supervisor
  farsee                    Survey all legions (stage, attention, criteria)
  behold <id>              Behold one legion: stage, supervisor liveness, criteria
  send-word <id> <msg>     Send composer-guarded word to a role window (--window, default: command)
  answer <id> <msg>        Answer a holding legion's question and resume it
  grant <id>               Grant a cleared_for_human legion (closes it, routes memory)
  banish <id> [--force]    Banish a legion; refuses in-flight work without --force
  keep-watch <id> [--stop] Keep or stop watch over the legion
  trial <id>               Put acceptance criteria to machine trial

The stone:
  (no command)             Open the seeing-stone dashboard (Textual, via uv)
  statusline               Emit a tmux status-right fragment

Foundations:
  doctor                   Check dependencies and state home
  composer <sub>           Pane composer classifier (classify / strip / idle)
  state <sub>              Legion manifest I/O (ls / new / show / event / paths / doctor)

Options:
  -h, --help               Show this help message
EOF
}

if [ $# -eq 0 ]; then
  exec uv run "$SCRIPT_DIR/dashboard.py"
fi

case "$1" in
  -h | --help | help)
    show_usage
    exit 0
    ;;
  summon)
    shift
    exec bash "$SCRIPT_DIR/summon.sh" "$@"
    ;;
  banish)
    shift
    require_human_control banish
    exec bash "$SCRIPT_DIR/banish.sh" "$@"
    ;;
  farsee)
    shift
    exec python3 "$SCRIPT_DIR/legion_state.py" ls "$@"
    ;;
  behold)
    shift
    exec python3 "$SCRIPT_DIR/supervisor.py" status "$@"
    ;;
  send-word)
    shift
    legion_id="${1:?usage: ,palantir send-word <id> [--window W] <msg>}"
    shift
    window="command"
    if [ "${1:-}" = "--window" ]; then
      window="${2:?--window needs a value}"
      shift 2
    fi
    exec python3 "$SCRIPT_DIR/panes.py" send-word "$legion_id" --window "$window" --text "${*:?send-word needs a message}"
    ;;
  answer)
    shift
    legion_id="${1:?usage: ,palantir answer <id> <msg>}"
    shift
    text="${*:?answer needs a message}"
    exec python3 "$SCRIPT_DIR/supervisor.py" dispatch "$legion_id" \
      --json-event "$(python3 -c 'import json,sys; print(json.dumps({"kind":"answer","text":sys.argv[1]}))' "$text")"
    ;;
  grant)
    shift
    require_human_control grant
    legion_id="${1:?usage: ,palantir grant <id>}"
    exec python3 "$SCRIPT_DIR/supervisor.py" dispatch "$legion_id" --json-event '{"kind":"grant_clear"}'
    ;;
  keep-watch)
    shift
    legion_id="${1:?usage: ,palantir keep-watch <id> [--stop]}"
    if [ "${2:-}" = "--stop" ]; then
      exec python3 "$SCRIPT_DIR/supervisor.py" stop "$legion_id"
    fi
    exec python3 "$SCRIPT_DIR/supervisor.py" run "$legion_id"
    ;;
  trial)
    shift
    exec python3 "$SCRIPT_DIR/supervisor.py" verify "$@"
    ;;
  statusline)
    shift
    exec python3 "$SCRIPT_DIR/statusline.py" "$@"
    ;;
  doctor)
    shift
    exec python3 "$SCRIPT_DIR/legion_state.py" doctor "$@"
    ;;
  composer)
    shift
    exec python3 "$SCRIPT_DIR/composer.py" "$@"
    ;;
  state)
    shift
    exec python3 "$SCRIPT_DIR/legion_state.py" "$@"
    ;;
  dashboard)
    shift
    exec uv run "$SCRIPT_DIR/dashboard.py" "$@"
    ;;
  *)
    echo "Error: Unknown command '$1'" >&2
    echo >&2
    show_usage
    exit 1
    ;;
esac
