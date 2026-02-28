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

declare -a sess=()
declare -a dirs_to_remove=()
declare -a wt_paths=()

while IFS= read -r _line; do
  [ -n "$_line" ] || continue
  mapfile -t _fields < <(awk -F $'\t' '{print $1; print $2; print $3; print $4; print $5}' <<<"$_line")
  kind="${_fields[1]-}"
  path="${_fields[2]-}"
  target="${_fields[4]-}"

  if [ "$kind" = "session" ] && [ -n "$target" ]; then
    sess+=("$target")
  elif [ "$kind" = "dir" ]; then
    if [ -n "$path" ]; then
      dirs_to_remove+=("$path")
    fi
  elif [ "$kind" = "worktree" ]; then
    if [ -n "$path" ]; then
      wt_paths+=("$path")
    fi
  fi
done <"$sel_file"

declare -a paths_to_check=("${dirs_to_remove[@]}" "${wt_paths[@]}")

if [ ${#paths_to_check[@]} -gt 0 ] && command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  while IFS=$'\t' read -r name spath; do
    [ -n "$name" ] || continue
    [ -n "$spath" ] || continue
    spath="$(realpath "$spath" 2>/dev/null || printf '%s' "$spath")"
    for d in "${paths_to_check[@]}"; do
      rd="$(realpath "$d" 2>/dev/null || printf '%s' "$d")"
      if [ "$spath" = "$rd" ] || [[ "$spath" == "$rd"/* ]]; then
        sess+=("$name")
        break
      fi
    done
  done < <(tmux list-sessions -F $'#{session_name}\t#{session_path}' 2>/dev/null || true)
fi

if [ ${#dirs_to_remove[@]} -gt 0 ] && command -v zoxide >/dev/null 2>&1; then
  for d in "${dirs_to_remove[@]}"; do
    zoxide remove "$d" 2>/dev/null || true
  done
fi

if [ ${#sess[@]} -gt 0 ]; then
  mapfile -t sess < <(printf '%s\n' "${sess[@]}" | sort -u)
fi

[ ${#sess[@]} -gt 0 ] || [ ${#dirs_to_remove[@]} -gt 0 ] || exit 0

if [ ${#sess[@]} -gt 0 ] && command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  for s in "${sess[@]}"; do
    tmux kill-session -t "$s" 2>/dev/null || true
  done
fi

now_epoch="$(date +%s)"
{
  for s in "${sess[@]}"; do
    [ -n "$s" ] || continue
    printf '%s\tSESSION_TARGET\t%s\n' "$now_epoch" "$s"
  done
  for d in "${dirs_to_remove[@]}"; do
    [ -n "$d" ] || continue
    printf '%s\tPATH_PREFIX\t%s\n' "$now_epoch" "$d"
  done
} >>"$mutation_file"

if [ ! -f "$cache_file" ]; then
  exit 0
fi

if ! acquire_lock; then
  exit 0
fi
trap release_lock EXIT

CACHE_FILE="$cache_file" SESSIONS="$(printf '%s\n' "${sess[@]}")" DIRS="$(printf '%s\n' "${dirs_to_remove[@]}")" python3 - <<'PY'
import os
import sys

cache_file = os.environ["CACHE_FILE"]
sel = os.environ["SESSIONS"].split("\n")
sel = { s for s in sel if s }
dirs = os.environ["DIRS"].split("\n")
dirs = { d for d in dirs if d }

out = []
with open(cache_file, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 5:
            continue
        kind = parts[1]
        path = parts[2]
        target = parts[4]

        if kind == "dir" and path in dirs:
            continue

        out.append(line)

tmp = cache_file + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    f.writelines(out)
os.replace(tmp, cache_file)
PY
