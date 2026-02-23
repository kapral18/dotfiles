#!/usr/bin/env bash
set -euo pipefail

sel_file="${1:-}"
if [ -z "$sel_file" ] || [ ! -f "$sel_file" ]; then
  exit 0
fi

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
pending_file="${cache_dir}/pick_session_pending.tsv"
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

worktree_root_dir_for_path() {
  local p="$1"
  [ -n "$p" ] || return 1
  [ -d "$p" ] || return 1

  if [ -d "$p/.git" ]; then
    realpath "$p" 2>/dev/null || printf '%s\n' "$p"
    return 0
  fi

  if [ -f "$p/.git" ]; then
    local gitdir
    gitdir="$(sed -n '1s/^gitdir: //p' "$p/.git" 2>/dev/null | head -n 1 || true)"
    [ -n "$gitdir" ] || return 1
    case "$gitdir" in
      /*) ;;
      *) gitdir="$p/$gitdir" ;;
    esac
    gitdir="$(realpath "$gitdir" 2>/dev/null || printf '%s' "$gitdir")"
    case "$gitdir" in
      */.git/worktrees/*)
        printf '%s\n' "$(dirname "$(dirname "$(dirname "$gitdir")")")"
        return 0
        ;;
    esac
  fi

  local common common_path
  common="$(git -C "$p" rev-parse --git-common-dir 2>/dev/null || true)"
  [ -n "$common" ] || return 1
  case "$common" in
    /*) common_path="$common" ;;
    *) common_path="$p/$common" ;;
  esac
  common_path="$(realpath "$common_path" 2>/dev/null || printf '%s' "$common_path")"
  dirname "$common_path"
}

remove_paths_in_background() {
  local root="$1"
  shift
  local -a paths=( "$@" )
  [ ${#paths[@]} -gt 0 ] || return 0

  if ! command -v ,w >/dev/null 2>&1; then
    tmux display-message "tmux: missing command: ,w"
    return 0
  fi

  local cmd
  cmd="cd $(printf %q "$root") && ,w remove --tmux-notify --paths"
  local p
  for p in "${paths[@]}"; do
    cmd+=" $(printf %q "$p")"
  done
  tmux run-shell -b "$cmd"
}

declare -A roots_selected=()
declare -A worktree_paths_by_root=()
declare -a pending_wt_paths=()

while IFS=$'\t' read -r _display kind path meta target; do
  [ -n "$kind" ] || continue
  [ -n "$path" ] || continue

  meta_base="${meta%%|*}"
  wt_path=""
  root_wt_dir=""

  case "$kind" in
    worktree)
      wt_path="$path"
      root_wt_dir="$target"
      ;;
    session)
      case "$meta_base" in
        sess_root:*|sess_wt:*)
          wt_path="$path"
          root_wt_dir="$(worktree_root_dir_for_path "$path" 2>/dev/null || true)"
          ;;
      esac
      ;;
  esac

  [ -n "$wt_path" ] || continue
  [ -n "$root_wt_dir" ] || continue

  case "$meta_base" in
    wt_root:*|sess_root:*) roots_selected["$root_wt_dir"]=1 ;;
  esac

  worktree_paths_by_root["$root_wt_dir"]+=$'\n'"$wt_path"
  pending_wt_paths+=( "$wt_path" )
done <"$sel_file"

[ ${#pending_wt_paths[@]} -gt 0 ] || exit 0

# Record pending worktree removals so a subsequent index refresh doesn't re-add them.
{
  for p in "${pending_wt_paths[@]}"; do
    printf 'WT\t%s\n' "$p"
  done
} >>"$pending_file"

# Record path tombstones so long-running/stale scans cannot resurrect removed
# rows while the actual filesystem cleanup is still in flight.
now_epoch="$(date +%s)"
{
  for p in "${pending_wt_paths[@]}"; do
    [ -n "$p" ] || continue
    printf '%s\tPATH_PREFIX\t%s\n' "$now_epoch" "$p"
  done
} >>"$mutation_file"

if command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  for root in "${!roots_selected[@]}"; do
    tmux run-shell -b "$HOME/.config/tmux/scripts/pick_session_remove_all_worktrees.sh $(printf %q "$root")"
  done

  for root in "${!worktree_paths_by_root[@]}"; do
    if [ -n "${roots_selected["$root"]+x}" ]; then
      continue
    fi
    mapfile -t paths < <(printf '%s\n' "${worktree_paths_by_root[$root]}" | sed '/^$/d' | sort -u)
    if [ ${#paths[@]} -gt 0 ]; then
      remove_paths_in_background "$root" "${paths[@]}"
    fi
  done
fi

# Prune selected worktrees (and their session rows) from the cache immediately.
if [ -f "$cache_file" ] && acquire_lock; then
  trap release_lock EXIT

  CACHE_FILE="$cache_file" PENDING_WT="$(printf '%s\n' "${pending_wt_paths[@]}")" python3 - <<'PY'
import os
from pathlib import Path

cache_file = os.environ["CACHE_FILE"]
paths = { p for p in os.environ["PENDING_WT"].split("\n") if p }

def should_drop(kind, p):
    if not p:
        return False
    for base in paths:
        if p == base or p.startswith(base + "/"):
            # Drop dir rows under removed worktrees too.
            if kind in ("dir", "worktree", "session"):
                return True
    return False

out = []
with open(cache_file, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 5:
            continue
        kind = parts[1]
        path = parts[2]
        if should_drop(kind, path):
            continue
        out.append(line)

tmp = cache_file + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    f.writelines(out)
os.replace(tmp, cache_file)
PY
fi
