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

realpath_or_self() {
  realpath "$1" 2>/dev/null || printf '%s' "$1"
}

repo_name_from_remote() {
  local dir="$1"
  local url=""
  url="$(git -C "$dir" remote get-url origin 2>/dev/null || true)"
  if [ -z "$url" ]; then
    url="$(git -C "$dir" remote get-url upstream 2>/dev/null || true)"
  fi
  [ -n "$url" ] || return 1

  url="${url%/}"
  url="${url%.git}"

  local name="$url"
  case "$url" in
  *://*) name="${url##*/}" ;;
  *:*)
    name="${url#*:}"
    name="${name##*/}"
    ;;
  *) name="${url##*/}" ;;
  esac
  [ -n "$name" ] || return 1
  printf '%s\n' "$name"
}

nuke_dir_for_root_worktree() {
  local root="$1"
  [ -n "$root" ] || return 1
  root="$(realpath_or_self "$root")"
  [ -d "$root" ] || {
    printf '%s\n' "$root"
    return 0
  }

  local repo_name wrapper
  repo_name="$(repo_name_from_remote "$root" 2>/dev/null || true)"
  wrapper="$(realpath_or_self "$(dirname "$root")")"

  if [ -n "$repo_name" ] && [ "$(basename "$wrapper")" = "$repo_name" ]; then
    case "$wrapper" in
    "" | "/") ;;
    *)
      if [ -n "${HOME:-}" ] && [ "$wrapper" = "$(realpath_or_self "$HOME")" ]; then
        printf '%s\n' "$root"
        return 0
      fi
      printf '%s\n' "$wrapper"
      return 0
      ;;
    esac
  fi

  printf '%s\n' "$root"
}

list_worktree_paths() {
  local root="$1"
  [ -n "$root" ] || return 1
  git -C "$root" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2}' | sed '/^$/d' || true
}

worktree_root_dir_for_path() {
  local p="$1"
  [ -n "$p" ] || return 1
  [ -d "$p" ] || return 1

  p="$(realpath_or_self "$p")"

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

worktree_dir_for_path() {
  local p="$1"
  [ -n "$p" ] || return 1

  p="$(realpath_or_self "$p")"
  if [ -f "$p" ]; then
    p="$(dirname "$p")"
  fi

  local cur="$p"
  local i=0
  while [ -n "$cur" ] && [ "$cur" != "/" ] && [ $i -lt 16 ]; do
    if [ -e "$cur/.git" ]; then
      printf '%s\n' "$cur"
      return 0
    fi
    cur="$(dirname "$cur")"
    i="$((i + 1))"
  done

  return 1
}

remove_paths_in_background() {
  local root="$1"
  shift
  local -a paths=("$@")
  [ ${#paths[@]} -gt 0 ] || return 0

  if ! command -v ,w >/dev/null 2>&1; then
    tmux display-message "tmux: missing command: ,w"
    return 0
  fi

  # Detach removal work from the picker UI:
  # - Do not use tmux `run-shell` (can steal popup focus).
  # - Unset TMUX vars so `,w` won't `display-message` spam.
  local cmd
  cmd="cd $(printf %q "$root") && env -u TMUX -u TMUX_PANE ,w remove --paths"
  local p
  for p in "${paths[@]}"; do
    cmd+=" $(printf %q "$p")"
  done
  nohup sh -c "$cmd" </dev/null >/dev/null 2>&1 &
}

declare -A roots_selected=()
declare -A worktree_paths_by_root=()
declare -a pending_wt_paths=()

while IFS= read -r _line; do
  [ -n "$_line" ] || continue
  mapfile -t _fields < <(awk -F $'\t' '{print $1; print $2; print $3; print $4; print $5}' <<<"$_line")
  kind="${_fields[1]-}"
  path="${_fields[2]-}"
  meta="${_fields[3]-}"
  target="${_fields[4]-}"

  [ -n "$kind" ] || continue
  [ -n "$path" ] || continue

  meta_base="${meta%%|*}"
  wt_path=""
  root_wt_dir=""
  is_root_selection=0

  case "$kind" in
  worktree)
    wt_path="$path"
    root_wt_dir="$target"
    case "$meta_base" in
    wt_root:*) is_root_selection=1 ;;
    esac
    ;;
  session)
    wt_path="$(worktree_dir_for_path "$path" 2>/dev/null || true)"
    if [ -z "$wt_path" ] && [ -n "${target:-}" ] && [ -f "$cache_file" ]; then
      # Fallback: if the selected row came from the live session overlay (or
      # otherwise has a non-git path), try to map the session name back to a
      # cached worktree-backed session row.
      cached="$(
        awk -F $'\t' -v t="$target" '
            $2 == "session" && $5 == t { print $3 "\t" $4; exit }
          ' "$cache_file" 2>/dev/null || true
      )"
      if [ -n "$cached" ]; then
        IFS=$'\t' read -r cached_path cached_meta <<<"$cached"
        if [ -n "$cached_path" ]; then
          wt_path="$(realpath_or_self "$cached_path")"
        fi
        if [ -n "$cached_meta" ]; then
          meta_base="${cached_meta%%|*}"
        fi
      fi
    fi

    [ -n "$wt_path" ] || continue
    root_wt_dir="$(worktree_root_dir_for_path "$wt_path" 2>/dev/null || true)"
    case "$meta_base" in
    sess_root:*) is_root_selection=1 ;;
    esac
    ;;
  esac

  [ -n "$wt_path" ] || continue
  [ -n "$root_wt_dir" ] || continue

  wt_path="$(realpath_or_self "$wt_path")"
  root_wt_dir="$(realpath_or_self "$root_wt_dir")"

  if [ "$wt_path" = "$root_wt_dir" ]; then
    is_root_selection=1
  fi

  if [ "$is_root_selection" -eq 1 ]; then
    roots_selected["$root_wt_dir"]=1

    base="$(nuke_dir_for_root_worktree "$root_wt_dir" 2>/dev/null || printf '%s' "$root_wt_dir")"
    base="$(realpath_or_self "$base")"
    pending_wt_paths+=("$base")

    while IFS= read -r p; do
      [ -n "$p" ] || continue
      pending_wt_paths+=("$(realpath_or_self "$p")")
    done < <(list_worktree_paths "$root_wt_dir")

    continue
  fi

  worktree_paths_by_root["$root_wt_dir"]+=$'\n'"$wt_path"
  pending_wt_paths+=("$wt_path")
done <"$sel_file"

if [ ${#pending_wt_paths[@]} -eq 0 ]; then
  if command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
    tmux display-message -d 4000 "pick_session: selection contains no worktrees" 2>/dev/null || true
  fi
  exit 0
fi
mapfile -t pending_wt_paths < <(printf '%s\n' "${pending_wt_paths[@]}" | sed '/^$/d' | LC_ALL=C sort -u)

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
    nohup env -u TMUX -u TMUX_PANE "$HOME/.config/tmux/scripts/pick_session_remove_all_worktrees.sh" "$root" </dev/null >/dev/null 2>&1 &
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
