#!/usr/bin/env bash
# Fetch PRs and issues from GitHub using search sections defined in gh-picker config.
# Outputs TSV rows for fzf consumption.
#
# Usage: gh_items.sh [--scope all|focus|explore] [--refresh] [--cache-only]
set -euo pipefail

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
mkdir -p "$cache_dir" 2> /dev/null || true

scope="${GH_PICKER_SCOPE:-all}"
refresh=0
cache_only=0

while [ $# -gt 0 ]; do
  case "$1" in
    --scope)
      scope="$2"
      shift 2
      ;;
    --scope=*)
      scope="${1#--scope=}"
      shift
      ;;
    --refresh)
      refresh=1
      shift
      ;;
    --cache-only)
      cache_only=1
      shift
      ;;
    *) shift ;;
  esac
done

script_dir="$(cd "$(dirname "$0")" && pwd)"
config="$script_dir/gh-picker.yml"

if [ ! -f "$config" ]; then
  printf 'Config not found: %s\n' "$config" >&2
  exit 1
fi

cache_file="${cache_dir}/gh_picker.tsv"
cache_ttl=300

emit_cache() {
  [ -f "$cache_file" ] || return 1
  python3 -u "$script_dir/lib/gh_items_main.py" \
    --config "$config" \
    --cache-file "$cache_file" \
    --scope "$scope" \
    --filter-cache
}

if [ "$cache_only" -eq 1 ]; then
  if ! emit_cache; then
    printf '\033[2;38;5;244m  Loading…\033[0m\theader\t\t\t\t\t\n'
  fi
  exit 0
fi

lock_helper="$script_dir/lib/gh_fetch_lock.py"
refresh_args=()
[ "$refresh" -eq 0 ] || refresh_args=(--refresh)
while true; do
  status="$(python3 "$lock_helper" acquire "$cache_file" "$$" ${refresh_args[@]+"${refresh_args[@]}"})"
  case "$status" in
    owned\ *)
      generation="${status#owned }"
      break
      ;;
    publishing) sleep 0.1 ;;
    busy)
      emit_cache || true
      exit 0
      ;;
    *) exit 1 ;;
  esac
done

PYTHON_PID=""
cleanup() {
  python3 "$lock_helper" release "$cache_file" "$$" "$generation" "$PYTHON_PID" || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

if [ "$refresh" -eq 0 ] && [ -f "$cache_file" ]; then
  mt="$(stat -c %Y "$cache_file" 2> /dev/null || stat -f %m "$cache_file" 2> /dev/null || echo 0)"
  now="$(date +%s)"
  age="$((now - mt))"
  if [ "$age" -ge 0 ] && [ "$age" -lt "$cache_ttl" ]; then
    emit_cache || true
    exit 0
  fi
fi

for cmd in gh yq python3; do
  command -v "$cmd" > /dev/null 2>&1 || {
    printf '%s not found\n' "$cmd" >&2
    exit 1
  }
done

if [ "$refresh" -eq 1 ]; then
  python3 -u "$script_dir/lib/gh_items_main.py" --config "$config" --cache-file "$cache_file" --scope "$scope" --refresh &
else
  python3 -u "$script_dir/lib/gh_items_main.py" --config "$config" --cache-file "$cache_file" --scope "$scope" &
fi
PYTHON_PID=$!
set +e
wait "$PYTHON_PID"
rc=$? PYTHON_PID=""
set -e
exit "$rc"
