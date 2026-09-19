#!/usr/bin/env bash
# Description: Control and launch the local llama.cpp router server.

set -euo pipefail

LLAMA_CPP_HOST="${LLAMA_CPP_HOST:-127.0.0.1}"
LLAMA_CPP_PORT="${LLAMA_CPP_PORT:-8080}"
LLAMA_CPP_API_KEY="${LLAMA_CPP_API_KEY:-}"
LLAMA_CPP_MODELS_PRESET="${LLAMA_CPP_MODELS_PRESET:-$HOME/.config/llama.cpp/models.ini}"
LLAMA_CPP_GRACE_SECONDS="${LLAMA_CPP_GRACE_SECONDS:-600}"
LLAMA_CPP_PRISM_ROOT="${LLAMA_CPP_PRISM_ROOT:-$HOME/.llama.cpp/prism}"
LLAMA_CPP_SERVER_BIN="${LLAMA_CPP_SERVER_BIN:-}"

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
  build-prism [opts]    Build and install the PrismML llama.cpp fork server.
                        Options: --tag <prism-tag> (default: newest prism-* tag),
                        --force (rebuild even when the tag is already installed).
  help                  Show this message.

Environment:
  LLAMA_CPP_HOST           Default: 127.0.0.1
  LLAMA_CPP_PORT           Default: 8080
  LLAMA_CPP_API_KEY        Sent as Authorization: Bearer <key> when set.
  LLAMA_CPP_MODELS_PRESET  Default: ~/.config/llama.cpp/models.ini
  LLAMA_CPP_LIFECYCLE_DIR  Default: ~/.local/state/llama-cpp/lifecycle
  LLAMA_CPP_GRACE_SECONDS  Default: 600. Use 0 for immediate shutdown.
  LLAMA_CPP_PRISM_ROOT     Default: ~/.llama.cpp/prism. PrismML fork checkout
                           ($root/llama.cpp) and installed binaries ($root/bin).
  LLAMA_CPP_SERVER_BIN     Explicit llama-server path or PATH name. Unset by default.

Server binary resolution (serve and run):
  1. $LLAMA_CPP_SERVER_BIN when set
  2. $LLAMA_CPP_PRISM_ROOT/bin/llama-server when it is an executable file
  3. llama-server from PATH (Homebrew llama.cpp)

Examples:
  ,llama-cpp serve
  ,llama-cpp run -- command args...
  ,llama-cpp status
  ,llama-cpp load nemotron-3.5
  ,llama-cpp load qwen3.6-35b-a3b
  ,llama-cpp unload --all
  ,llama-cpp build-prism
  ,llama-cpp build-prism --tag prism-b10687-5d80cff --force
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

  export LLAMA_CPP_HOST LLAMA_CPP_PORT LLAMA_CPP_API_KEY LLAMA_CPP_MODELS_PRESET LLAMA_CPP_GRACE_SECONDS LLAMA_CPP_PRISM_ROOT
  exec python3 "$HOME/lib/,llama-cpp/lifecycle.py" run -- "$@"
}

cmd_stop() {
  export LLAMA_CPP_HOST LLAMA_CPP_PORT LLAMA_CPP_API_KEY LLAMA_CPP_MODELS_PRESET LLAMA_CPP_GRACE_SECONDS LLAMA_CPP_PRISM_ROOT
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

prism_server_bin() {
  printf '%s\n' "${LLAMA_CPP_PRISM_ROOT}/bin/llama-server"
}

# Resolution order: LLAMA_CPP_SERVER_BIN, then the PrismML fork build, then PATH.
resolve_server_bin() {
  if [[ -n "$LLAMA_CPP_SERVER_BIN" ]]; then
    if [[ "$LLAMA_CPP_SERVER_BIN" == */* ]]; then
      if [[ -f "$LLAMA_CPP_SERVER_BIN" && -x "$LLAMA_CPP_SERVER_BIN" ]]; then
        printf '%s\n' "$LLAMA_CPP_SERVER_BIN"
        return 0
      fi
    else
      local found
      found=$(command -v "$LLAMA_CPP_SERVER_BIN" 2> /dev/null) && {
        printf '%s\n' "$found"
        return 0
      }
    fi
    return 1
  fi

  local prism
  prism=$(prism_server_bin)
  if [[ -f "$prism" && -x "$prism" ]]; then
    printf '%s\n' "$prism"
    return 0
  fi

  local path_bin
  path_bin=$(command -v llama-server 2> /dev/null) && {
    printf '%s\n' "$path_bin"
    return 0
  }
  return 1
}

cmd_serve() {
  local server_bin
  server_bin=$(resolve_server_bin) || {
    echo "Error: no llama-server executable found. Tried:" >&2
    echo "       1. LLAMA_CPP_SERVER_BIN=${LLAMA_CPP_SERVER_BIN:-<unset>}" >&2
    echo "       2. $(prism_server_bin) (build it with ',llama-cpp build-prism')" >&2
    echo "       3. llama-server on PATH (expected via Brewfile: brew \"llama.cpp\")" >&2
    exit 127
  }

  if [[ ! -f "$LLAMA_CPP_MODELS_PRESET" ]]; then
    echo "Error: llama.cpp models preset not found at $LLAMA_CPP_MODELS_PRESET." >&2
    echo "       Run 'chezmoi apply' to deploy home/dot_config/llama.cpp/models.ini.tmpl." >&2
    exit 1
  fi

  exec "$server_bin" \
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

LLAMA_CPP_PRISM_REPO="${LLAMA_CPP_PRISM_REPO:-https://github.com/PrismML-Eng/llama.cpp}"

cmd_build_prism() {
  local tag=""
  local force=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --tag)
        [[ $# -ge 2 ]] || {
          echo "Error: --tag requires a value" >&2
          exit 1
        }
        tag="$2"
        shift
        ;;
      --tag=*) tag="${1#--tag=}" ;;
      -f | --force) force=1 ;;
      -*)
        echo "Unknown option: $1" >&2
        exit 1
        ;;
      *)
        echo "Unknown argument: $1" >&2
        exit 1
        ;;
    esac
    shift
  done

  local dep
  for dep in git cmake; do
    command -v "$dep" > /dev/null 2>&1 || {
      echo "Error: $dep is required to build the PrismML fork (brew install $dep)" >&2
      exit 127
    }
  done

  local src="${LLAMA_CPP_PRISM_ROOT}/llama.cpp"
  local build="${src}/build"
  local bin_dir="${LLAMA_CPP_PRISM_ROOT}/bin"
  local tag_file="${bin_dir}/.tag"
  local server_bin
  server_bin=$(prism_server_bin)

  if [[ -d "$src/.git" ]]; then
    echo "Fetching tags in $src"
    git -C "$src" fetch --tags --prune
  else
    echo "Cloning $LLAMA_CPP_PRISM_REPO into $src"
    mkdir -p "$LLAMA_CPP_PRISM_ROOT"
    git clone "$LLAMA_CPP_PRISM_REPO" "$src"
  fi

  if [[ -z "$tag" ]]; then
    tag=$(git -C "$src" tag --list 'prism-*' --sort=-creatordate | head -n 1)
    [[ -n "$tag" ]] || {
      echo "Error: no prism-* tag found in $src" >&2
      exit 1
    }
  fi

  if [[ $force -eq 0 && -f "$tag_file" && -x "$server_bin" ]]; then
    if [[ "$(cat "$tag_file")" == "$tag" ]]; then
      echo "up to date (${tag})"
      exit 0
    fi
  fi

  echo "Building PrismML llama.cpp ${tag}"
  git -C "$src" checkout --quiet "$tag"
  cmake -B "$build" -S "$src" \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLAMA_BUILD_TESTS=OFF \
    -DLLAMA_BUILD_EXAMPLES=OFF \
    -DLLAMA_BUILD_TOOLS=ON \
    -DLLAMA_CURL=ON
  cmake --build "$build" -j --target llama-server llama-cli llama-bench

  mkdir -p "$bin_dir"
  local artifact
  for artifact in llama-server llama-cli llama-bench; do
    [[ -f "$build/bin/$artifact" ]] || {
      echo "Error: build did not produce $build/bin/$artifact" >&2
      exit 1
    }
    cp "$build/bin/$artifact" "$bin_dir/$artifact"
  done
  local library
  for library in "$build"/bin/lib*.dylib "$build"/bin/lib*.so; do
    if [[ -f "$library" ]]; then
      cp "$library" "$bin_dir/"
    fi
  done

  printf '%s\n' "$tag" > "$tag_file"
  echo "Installed ${tag} into ${bin_dir}"
  "$server_bin" --version
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
  build-prism) cmd_build_prism "$@" ;;
  help | -h | --help) show_usage ;;
  *)
    echo "Unknown subcommand: $subcommand" >&2
    show_usage >&2
    exit 1
    ;;
esac
