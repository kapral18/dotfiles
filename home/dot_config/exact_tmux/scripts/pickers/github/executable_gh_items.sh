#!/usr/bin/env bash
# Fetch PRs and issues from GitHub using search sections defined in gh-picker config.
# Outputs TSV rows for fzf consumption.
#
# Usage: gh_items.sh [--mode work|home] [--refresh]
set -euo pipefail

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
mkdir -p "$cache_dir" 2> /dev/null || true

mode="${GH_PICKER_MODE:-work}"
refresh=0
cache_only=0

while [ $# -gt 0 ]; do
  case "$1" in
    --mode)
      mode="$2"
      shift 2
      ;;
    --mode=*)
      mode="${1#--mode=}"
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
config=""
if [ "$mode" = "home" ]; then
  config="$script_dir/gh-picker-home.yml"
else
  config="$script_dir/gh-picker-work.yml"
fi

if [ ! -f "$config" ]; then
  printf 'Config not found: %s\n' "$config" >&2
  exit 1
fi

cache_file="${cache_dir}/gh_picker_${mode}.tsv"
cache_ttl=300

if [ "$cache_only" -eq 1 ]; then
  if [ -f "$cache_file" ]; then
    cat "$cache_file"
  else
    printf '\033[2;38;5;244m  Loading…\033[0m\theader\t\t\t\t\t\n'
  fi
  exit 0
fi

lock_dir="${cache_file}.lock"
while ! mkdir "$lock_dir" 2> /dev/null; do
  pid_file="${lock_dir}/pid"
  pid=""
  [ -f "$pid_file" ] && pid="$(cat "$pid_file" 2> /dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2> /dev/null; then
    if [ "$refresh" -eq 1 ]; then
      # Don't let a stuck/slow fetch block a manual refresh forever.
      waited=0
      while kill -0 "$pid" 2> /dev/null && [ "$waited" -lt 25 ]; do
        sleep 0.2
        waited="$((waited + 1))"
      done
      if kill -0 "$pid" 2> /dev/null; then
        kill "$pid" 2> /dev/null || true
        sleep 0.2
      fi
      rm -rf "$lock_dir" 2> /dev/null || true
      continue
    fi
    [ -f "$cache_file" ] && cat "$cache_file"
    exit 0
  fi
  rm -rf "$lock_dir" 2> /dev/null || true
done

cleanup_lock() {
  rm -f "${lock_dir}/pid" 2> /dev/null || true
  rmdir "$lock_dir" 2> /dev/null || true
}
trap cleanup_lock EXIT
printf '%s\n' "$$" > "${lock_dir}/pid" 2> /dev/null || true

if [ "$refresh" -eq 0 ] && [ -f "$cache_file" ]; then
  mt="$(stat -c %Y "$cache_file" 2> /dev/null || stat -f %m "$cache_file" 2> /dev/null || echo 0)"
  now="$(date +%s)"
  age="$((now - mt))"
  if [ "$age" -ge 0 ] && [ "$age" -lt "$cache_ttl" ]; then
    cat "$cache_file"
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
  python3 -u "$script_dir/lib/gh_items_main.py" --mode "$mode" --config "$config" --cache-file "$cache_file" --refresh
else
  python3 -u "$script_dir/lib/gh_items_main.py" --mode "$mode" --config "$config" --cache-file "$cache_file"
fi
