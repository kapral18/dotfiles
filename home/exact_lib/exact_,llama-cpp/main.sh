#!/usr/bin/env bash
# Description: Control and launch the local llama.cpp router server.

set -euo pipefail

LLAMA_CPP_HOST="${LLAMA_CPP_HOST:-127.0.0.1}"
LLAMA_CPP_PORT="${LLAMA_CPP_PORT:-8080}"
LLAMA_CPP_API_KEY="${LLAMA_CPP_API_KEY:-}"
LLAMA_CPP_MODELS_PRESET="${LLAMA_CPP_MODELS_PRESET:-$HOME/.config/llama.cpp/models.ini}"
LLAMA_CPP_GRACE_SECONDS="${LLAMA_CPP_GRACE_SECONDS:-600}"

base_url="http://${LLAMA_CPP_HOST}:${LLAMA_CPP_PORT}"

curl_args=(-sS)
if [[ -n "$LLAMA_CPP_API_KEY" ]]; then
  curl_args+=(-H "Authorization: Bearer ${LLAMA_CPP_API_KEY}")
fi

show_usage() {
  cat << 'EOF'
Usage: ,llama-cpp <subcommand> [args...]

Control a llama.cpp router server using its HTTP API. `run` joins a reachable
router or starts a loopback router and schedules its shutdown after the last consumer exits.

Subcommands:
  serve [args...]       Start llama-server in router mode with the local preset.
  run -- <command>      Run a command with a shared router lifecycle lease.
  stop [-f|--force]     Stop the lifecycle-owned router; --force interrupts active consumers.
  status                Show available models and router load state.
  load <model-id>...    Load one or more models.
  unload [id|--all]     Unload model(s). With --all, unload everything loaded.
  help                  Show this message.

Environment:
  LLAMA_CPP_HOST           Default: 127.0.0.1
  LLAMA_CPP_PORT           Default: 8080
  LLAMA_CPP_API_KEY        Sent as Authorization: Bearer <key> when set.
  LLAMA_CPP_MODELS_PRESET  Default: ~/.config/llama.cpp/models.ini
  LLAMA_CPP_LIFECYCLE_DIR  Default: ~/.local/state/llama-cpp/lifecycle
  LLAMA_CPP_GRACE_SECONDS  Default: 600. Use 0 for immediate shutdown.

Examples:
  ,llama-cpp serve
  ,llama-cpp run -- command args...
  ,llama-cpp status
  ,llama-cpp load local
  ,llama-cpp load local-max
  ,llama-cpp unload --all
EOF
}

cmd_run() {
  [[ $# -gt 0 ]] || {
    echo "Error: ,llama-cpp run requires a command after --" >&2
    exit 1
  }
  [[ "${1:-}" != "--" ]] || shift
  [[ $# -gt 0 ]] || {
    echo "Error: ,llama-cpp run requires a command after --" >&2
    exit 1
  }

  export LLAMA_CPP_HOST LLAMA_CPP_PORT LLAMA_CPP_API_KEY LLAMA_CPP_MODELS_PRESET LLAMA_CPP_GRACE_SECONDS
  exec python3 "$HOME/lib/,llama-cpp/lifecycle.py" run -- "$@"
}

cmd_stop() {
  export LLAMA_CPP_HOST LLAMA_CPP_PORT LLAMA_CPP_API_KEY LLAMA_CPP_MODELS_PRESET LLAMA_CPP_GRACE_SECONDS
  exec python3 "$HOME/lib/,llama-cpp/lifecycle.py" stop "$@"
}

require_jq() {
  command -v jq > /dev/null 2>&1 || {
    echo "Error: jq is required (brew install jq)" >&2
    exit 1
  }
}

json_escape() {
  jq -n --arg value "$1" '$value'
}

fetch_models() {
  curl "${curl_args[@]}" --max-time 15 -f "${base_url}/models"
}

cmd_serve() {
  if ! command -v llama-server > /dev/null 2>&1; then
    echo "Error: llama-server not found on PATH (expected via Brewfile: brew \"llama.cpp\")." >&2
    exit 127
  fi

  if [[ ! -f "$LLAMA_CPP_MODELS_PRESET" ]]; then
    echo "Error: llama.cpp models preset not found at $LLAMA_CPP_MODELS_PRESET." >&2
    echo "       Run 'chezmoi apply' to deploy home/dot_config/llama.cpp/models.ini.tmpl." >&2
    exit 1
  fi

  exec llama-server \
    --host "$LLAMA_CPP_HOST" \
    --port "$LLAMA_CPP_PORT" \
    --models-preset "$LLAMA_CPP_MODELS_PRESET" \
    "$@"
}

cmd_status() {
  require_jq
  local json
  json=$(fetch_models) || {
    echo "Error: llama.cpp router not reachable at ${base_url}" >&2
    exit 1
  }

  echo "Server: ${base_url}"
  echo ""
  printf '%s' "$json" | jq -r '
    (.data // [])
    | sort_by(.id)
    | .[]
    | .status.value as $status
    | (if $status == "loaded" then "[loaded]" elif $status == "loading" then "[loading]" else "[idle]" end) as $glyph
    | "  \($glyph) \(.id)  (\($status))"
  '
}

load_one() {
  local id="$1"
  local payload status body
  payload=$(printf '{"model":%s}' "$(json_escape "$id")")
  body=$(curl "${curl_args[@]}" --max-time 300 \
    -o /dev/stdout -w $'\n%{http_code}' \
    -X POST "${base_url}/models/load" \
    -H "Content-Type: application/json" \
    -d "$payload") || {
    echo "  -> ${id}: connection failed" >&2
    return 1
  }
  status="${body##*$'\n'}"
  body="${body%$'\n'*}"
  if [[ "$status" == "200" ]]; then
    echo "  -> ${id}: loaded"
  else
    echo "  -> ${id}: HTTP ${status}: ${body}" >&2
    return 1
  fi
}

unload_one() {
  local id="$1"
  local payload status body
  payload=$(printf '{"model":%s}' "$(json_escape "$id")")
  body=$(curl "${curl_args[@]}" --max-time 60 \
    -o /dev/stdout -w $'\n%{http_code}' \
    -X POST "${base_url}/models/unload" \
    -H "Content-Type: application/json" \
    -d "$payload") || {
    echo "  -> ${id}: connection failed" >&2
    return 1
  }
  status="${body##*$'\n'}"
  body="${body%$'\n'*}"
  if [[ "$status" == "200" ]]; then
    echo "  -> ${id}: unloaded"
  else
    echo "  -> ${id}: HTTP ${status}: ${body}" >&2
    return 1
  fi
}

cmd_load() {
  [[ $# -gt 0 ]] || {
    echo "Error: ,llama-cpp load requires at least one model id" >&2
    exit 1
  }
  require_jq

  local failures=0
  for id in "$@"; do
    load_one "$id" || failures=$((failures + 1))
  done
  [[ $failures -eq 0 ]] || exit 1
}

cmd_unload() {
  require_jq
  local all=0
  local ids=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -a | --all) all=1 ;;
      --)
        shift
        ids+=("$@")
        break
        ;;
      -*)
        echo "Unknown option: $1" >&2
        exit 1
        ;;
      *) ids+=("$1") ;;
    esac
    shift
  done

  if [[ $all -eq 1 ]]; then
    local json loaded
    json=$(fetch_models) || {
      echo "Error: llama.cpp router not reachable at ${base_url}" >&2
      exit 1
    }
    loaded=$(printf '%s' "$json" | jq -r '.data[]? | select(.status.value == "loaded") | .id')
    if [[ -z "$loaded" ]]; then
      echo "No models currently loaded on ${base_url}; nothing to do."
      return
    fi
    local failures=0
    while read -r id; do
      unload_one "$id" || failures=$((failures + 1))
    done <<< "$loaded"
    [[ $failures -eq 0 ]] || exit 1
    return
  fi

  [[ ${#ids[@]} -gt 0 ]] || {
    echo "Error: ,llama-cpp unload requires a model id, or --all" >&2
    exit 1
  }

  local failures=0
  for id in "${ids[@]}"; do
    unload_one "$id" || failures=$((failures + 1))
  done
  [[ $failures -eq 0 ]] || exit 1
}

subcommand="${1:-help}"
[[ $# -gt 0 ]] && shift || true

case "$subcommand" in
  serve) cmd_serve "$@" ;;
  run) cmd_run "$@" ;;
  stop) cmd_stop "$@" ;;
  status) cmd_status ;;
  load) cmd_load "$@" ;;
  unload) cmd_unload "$@" ;;
  help | -h | --help) show_usage ;;
  *)
    echo "Unknown subcommand: $subcommand" >&2
    show_usage >&2
    exit 1
    ;;
esac
