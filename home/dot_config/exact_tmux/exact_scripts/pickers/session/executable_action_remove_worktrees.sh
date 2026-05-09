#!/usr/bin/env bash
# Re-exec under a modern bash when macOS ships bash 3.2 as /bin/bash.
if [ "${BASH_VERSINFO[0]:-0}" -lt 4 ]; then
  for _b in /opt/homebrew/bin/bash /usr/local/bin/bash; do
    [ -x "$_b" ] && exec "$_b" "$0" "$@"
  done
  exit 1
fi
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"

sel_file="${1:-}"
if [ -z "$sel_file" ] || [ ! -f "$sel_file" ]; then
  exit 0
fi

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
pending_file="${cache_dir}/pick_session_pending.tsv"
pending_lock_dir="${pending_file}.lock"
mutation_file="${cache_dir}/pick_session_mutations.tsv"
rm_log_file="${cache_dir}/pick_session_remove_worktrees.log"
rm_log_max_lines=2000
mkdir -p "$cache_dir"

lock_dir="${cache_file}.lock"
acquire_lock() {
  local waited=0
  while ! mkdir "$lock_dir" 2> /dev/null; do
    sleep 0.02
    waited="$((waited + 20))"
    [ "$waited" -ge 200 ] && return 1
  done
  return 0
}
release_lock() { rmdir "$lock_dir" 2> /dev/null || true; }

# Serialize read-modify-write on `pending_file` across the picker, the async
# `remove_all_worktrees.sh` removers, and any other future writers. The same
# `mkdir`-based lock pattern is used elsewhere (cache_file).
acquire_pending_lock() {
  local waited=0
  while ! mkdir "$pending_lock_dir" 2> /dev/null; do
    sleep 0.02
    waited="$((waited + 20))"
    [ "$waited" -ge 1000 ] && return 1
  done
  return 0
}
release_pending_lock() { rmdir "$pending_lock_dir" 2> /dev/null || true; }

# `sel_file` is a per-binding snapshot minted by `dispatch_async.sh`. We're
# the last consumer of that snapshot, so unlink it on EXIT (covers normal
# completion, errors, and interrupts) along with releasing locks.
_action_remove_cleanup() {
  rm -f "$sel_file" 2> /dev/null || true
  release_lock
  release_pending_lock
}
trap _action_remove_cleanup EXIT

realpath_or_self() {
  realpath "$1" 2> /dev/null || printf '%s' "$1"
}

current_session=""
if command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  current_session="$(tmux display-message -p '#S' 2> /dev/null || true)"
fi

repo_name_from_remote() {
  local dir="$1"
  local url=""
  url="$(git -C "$dir" remote get-url origin 2> /dev/null || true)"
  if [ -z "$url" ]; then
    url="$(git -C "$dir" remote get-url upstream 2> /dev/null || true)"
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
  repo_name="$(repo_name_from_remote "$root" 2> /dev/null || true)"
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
  git -C "$root" worktree list --porcelain 2> /dev/null | awk '/^worktree /{print $2}' | sed '/^$/d' || true
}

worktree_root_dir_for_path() {
  local p="$1"
  [ -n "$p" ] || return 1
  [ -d "$p" ] || return 1

  p="$(realpath_or_self "$p")"

  if [ -d "$p/.git" ]; then
    realpath "$p" 2> /dev/null || printf '%s\n' "$p"
    return 0
  fi

  if [ -f "$p/.git" ]; then
    local gitdir
    gitdir="$(sed -n '1s/^gitdir: //p' "$p/.git" 2> /dev/null | head -n 1 || true)"
    [ -n "$gitdir" ] || return 1
    case "$gitdir" in
      /*) ;;
      *) gitdir="$p/$gitdir" ;;
    esac
    gitdir="$(realpath "$gitdir" 2> /dev/null || printf '%s' "$gitdir")"
    case "$gitdir" in
      */.git/worktrees/*)
        printf '%s\n' "$(dirname "$(dirname "$(dirname "$gitdir")")")"
        return 0
        ;;
    esac
  fi

  local common common_path
  common="$(git -C "$p" rev-parse --git-common-dir 2> /dev/null || true)"
  [ -n "$common" ] || return 1
  case "$common" in
    /*) common_path="$common" ;;
    *) common_path="$p/$common" ;;
  esac
  common_path="$(realpath "$common_path" 2> /dev/null || printf '%s' "$common_path")"
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

kill_tmux_sessions_for_paths() {
  local cur_sess="$1"
  shift || true
  local explicit_list="${1:-}"
  shift || true
  local -a paths=("$@")

  command -v tmux > /dev/null 2>&1 || return 0
  [ -n "${TMUX:-}" ] || return 0
  [ ${#paths[@]} -gt 0 ] || return 0

  local explicit_seen=" ${explicit_list} "
  local -a to_kill=()
  local to_kill_seen=" "

  _add_kill() {
    local name="$1"
    [ -n "$name" ] || return 0
    case "$to_kill_seen" in
      *" ${name} "*) return 0 ;;
    esac
    to_kill+=("$name")
    to_kill_seen+="${name} "
  }

  local sname spath rspath p rp
  while IFS=$'\t' read -r sname spath; do
    [ -n "$sname" ] || continue
    [ -n "$spath" ] || continue
    rspath="$(realpath_or_self "$spath")"
    for p in "${paths[@]}"; do
      [ -n "$p" ] || continue
      rp="$(realpath_or_self "$p")"
      if [ "$rspath" = "$rp" ]; then
        _add_kill "$sname"
        break
      fi
    done
  done < <(tmux list-sessions -F $'#{session_name}\t#{session_path}' 2> /dev/null || true)

  local s
  for s in "${to_kill[@]}"; do
    [ -n "$s" ] || continue
    if [ -n "$cur_sess" ] && [ "$s" = "$cur_sess" ]; then
      case "$explicit_seen" in
        *" ${s} "*) ;;
        *) continue ;;
      esac
    fi
    tmux kill-session -t "$s" 2> /dev/null || true
  done
}

remove_paths_in_background() {
  local root="$1"
  shift
  local -a paths=("$@")
  [ ${#paths[@]} -gt 0 ] || return 0

  if ! command -v ,w > /dev/null 2>&1; then
    tmux display-message "tmux: missing command: ,w"
    return 0
  fi

  # Detach removal work from the picker UI:
  # - Do not use tmux `run-shell` (can steal popup focus).
  # - Kill matching sessions ourselves (protecting the current session unless it
  #   was explicitly selected), then run `,w remove` with TMUX unset so it can't
  #   accidentally kill the current session by path.
  local cmd
  cmd="cd $(printf %q "$root") && ,w remove --paths"
  local p
  for p in "${paths[@]}"; do
    cmd+=" $(printf %q "$p")"
  done
  {
    printf '\n[%s] %s\n' "$(date +%Y-%m-%dT%H:%M:%S%z)" "$cmd"
  } >> "$rm_log_file" 2> /dev/null || true

  # Trim the log opportunistically so it can't grow without bound across
  # a long-running tmux server. We only trim when we're well past the cap to
  # avoid rewriting on every removal.
  if [ -f "$rm_log_file" ]; then
    local _lines
    _lines="$(wc -l < "$rm_log_file" 2> /dev/null | tr -d ' ' || echo 0)"
    case "${_lines:-0}" in
      '' | *[!0-9]*) _lines=0 ;;
    esac
    if [ "$_lines" -gt "$((rm_log_max_lines * 2))" ]; then
      local _trim_tmp
      _trim_tmp="$(mktemp "${rm_log_file}.trim.XXXXXX" 2> /dev/null || true)"
      if [ -n "$_trim_tmp" ]; then
        tail -n "$rm_log_max_lines" "$rm_log_file" > "$_trim_tmp" 2> /dev/null \
          && mv -f "$_trim_tmp" "$rm_log_file" 2> /dev/null || rm -f "$_trim_tmp" 2> /dev/null || true
      fi
    fi
  fi

  kill_tmux_sessions_for_paths "$current_session" "$explicit_sessions_list" "${paths[@]}" || true
  nohup env -u TMUX -u TMUX_PANE bash -c "$cmd" < /dev/null >> "$rm_log_file" 2>&1 &
}

declare -A roots_selected=()
declare -A worktree_paths_by_root=()
declare -a pending_wt_paths=()
declare -a pending_plain_dirs=()
explicit_sessions_list=""

while IFS= read -r _line; do
  [ -n "$_line" ] || continue
  mapfile -t _fields < <(awk -F $'\t' '{print $1; print $2; print $3; print $4; print $5}' <<< "$_line")
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
      if [ -n "${target:-}" ]; then
        explicit_sessions_list+="${target} "
      fi
      wt_path="$(worktree_dir_for_path "$path" 2> /dev/null || true)"
      if [ -z "$wt_path" ] && [ -n "${target:-}" ] && [ -f "$cache_file" ]; then
        # Fallback: if the selected row came from the live session overlay (or
        # otherwise has a non-git path), try to map the session name back to a
        # cached worktree-backed session row.
        cached="$(
          awk -F $'\t' -v t="$target" '
            $2 == "session" && $5 == t { print $3 "\t" $4; exit }
          ' "$cache_file" 2> /dev/null || true
        )"
        if [ -n "$cached" ]; then
          IFS=$'\t' read -r cached_path cached_meta <<< "$cached"
          if [ -n "$cached_path" ]; then
            wt_path="$(realpath_or_self "$cached_path")"
          fi
          if [ -n "$cached_meta" ]; then
            meta_base="${cached_meta%%|*}"
          fi
        fi
      fi

      if [ -z "$wt_path" ]; then
        pending_plain_dirs+=("$path")
        continue
      fi

      [ -n "$wt_path" ] || continue
      root_wt_dir="$(worktree_root_dir_for_path "$wt_path" 2> /dev/null || true)"
      case "$meta_base" in
        sess_root:*) is_root_selection=1 ;;
      esac
      ;;
    dir)
      pending_plain_dirs+=("$path")
      continue
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

    base="$(nuke_dir_for_root_worktree "$root_wt_dir" 2> /dev/null || printf '%s' "$root_wt_dir")"
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
done < "$sel_file"

if [ ${#pending_wt_paths[@]} -eq 0 ] && [ ${#pending_plain_dirs[@]} -eq 0 ]; then
  if command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
    tmux display-message -d 4000 "pick_session: selection contains nothing to remove" 2> /dev/null || true
  fi
  exit 0
fi

if [ ${#pending_wt_paths[@]} -gt 0 ]; then
  mapfile -t pending_wt_paths < <(printf '%s\n' "${pending_wt_paths[@]}" | sed '/^$/d' | LC_ALL=C sort -u)
fi
if [ ${#pending_plain_dirs[@]} -gt 0 ]; then
  mapfile -t pending_plain_dirs < <(printf '%s\n' "${pending_plain_dirs[@]}" | sed '/^$/d' | LC_ALL=C sort -u)
fi

# Record pending worktree removals so a subsequent index refresh doesn't re-add
# them. Serialized via `pending_lock_dir` so concurrent appenders/rewriters
# (this script + the async `remove_all_worktrees.sh` cleanup_pending_entries)
# can't interleave.
if [ ${#pending_wt_paths[@]} -gt 0 ]; then
  if acquire_pending_lock; then
    {
      for p in "${pending_wt_paths[@]}"; do
        printf 'WT\t%s\n' "$p"
      done
    } >> "$pending_file"
    release_pending_lock
  fi
fi

# Record path tombstones so long-running/stale scans cannot resurrect removed
# rows while the actual filesystem cleanup is still in flight.
now_epoch="$(date +%s)"
{
  for p in "${pending_wt_paths[@]}"; do
    [ -n "$p" ] || continue
    printf '%s\tPATH_PREFIX\t%s\n' "$now_epoch" "$p"
  done
  for p in "${pending_plain_dirs[@]}"; do
    [ -n "$p" ] || continue
    printf '%s\tPATH_PREFIX\t%s\n' "$now_epoch" "$p"
  done
} >> "$mutation_file"

if command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  for root in "${!roots_selected[@]}"; do
    nohup env -u TMUX -u TMUX_PANE PICK_SESSION_CURRENT_SESSION="$current_session" "$HOME/.config/tmux/scripts/pickers/session/remove_all_worktrees.sh" "$root" < /dev/null > /dev/null 2>&1 &
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

  if [ ${#pending_plain_dirs[@]} -gt 0 ]; then
    for pd in "${pending_plain_dirs[@]}"; do
      nohup env -u TMUX -u TMUX_PANE "$HOME/.config/tmux/scripts/pickers/session/remove_plain_dir.sh" "$pd" < /dev/null > /dev/null 2>&1 &
    done
  fi
fi

if [ ${#pending_plain_dirs[@]} -gt 0 ] && command -v zoxide > /dev/null 2>&1; then
  for pd in "${pending_plain_dirs[@]}"; do
    zoxide remove "$pd" 2> /dev/null || true
  done
fi

# Prune selected worktrees (and their session rows) from the cache immediately.
if [ -f "$cache_file" ] && acquire_lock; then
  CACHE_FILE="$cache_file" PENDING_WT="$(printf '%s\n' "${pending_wt_paths[@]-}")" PENDING_DIRS="$(printf '%s\n' "${pending_plain_dirs[@]-}")" python3 "$script_dir/lib/cache_prune_paths.py"
fi
