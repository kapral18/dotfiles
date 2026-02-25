#!/usr/bin/env bash
set -euo pipefail

sel_file="${1:-}"
if [ -z "$sel_file" ] || [ ! -f "$sel_file" ]; then
  exit 0
fi

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"
mkdir -p "$cache_dir"

lock_dir="${cache_file}.lock"
acquire_lock() {
  local waited=0
  while ! mkdir "$lock_dir" 2>/dev/null; do
    sleep 0.02
    waited="$((waited + 20))"
    [ "$waited" -ge 200 ] && return 1
  done
  return 0
}
release_lock() { rmdir "$lock_dir" 2>/dev/null || true; }

mapfile -t sess < <(awk -F $'\t' '$2 == "session" && $5 != "" { print $5 }' "$sel_file" 2>/dev/null || true)

[ ${#sess[@]} -gt 0 ] || exit 0

if command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  s=""
  for s in "${sess[@]}"; do
    tmux kill-session -t "$s" 2>/dev/null || true
  done
fi

now_epoch="$(date +%s)"
{
  s=""
  for s in "${sess[@]}"; do
    [ -n "$s" ] || continue
    printf '%s\tSESSION_TARGET\t%s\n' "$now_epoch" "$s"
  done
} >>"$mutation_file"

if [ ! -f "$cache_file" ]; then
  exit 0
fi

if ! acquire_lock; then
  exit 0
fi
trap release_lock EXIT

CACHE_FILE="$cache_file" SESSIONS="$(printf '%s\n' "${sess[@]}")" python3 - <<'PY'
import os
import sys

cache_file = os.environ["CACHE_FILE"]
sel = os.environ["SESSIONS"].split("\n")
sel = { s for s in sel if s }

out = []
with open(cache_file, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 5:
            continue
        kind = parts[1]
        target = parts[4]
        if kind == "session" and target in sel:
            continue
        out.append(line)

tmp = cache_file + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    f.writelines(out)
os.replace(tmp, cache_file)
PY
