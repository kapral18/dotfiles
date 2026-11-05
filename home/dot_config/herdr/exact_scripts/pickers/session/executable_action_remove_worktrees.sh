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

force_remove=0
check_only=0

while [ $# -gt 0 ]; do
  case "$1" in
    --force)
      force_remove=1
      shift
      ;;
    --check)
      check_only=1
      shift
      ;;
    --)
      shift
      break
      ;;
    -*)
      exit 2
      ;;
    *)
      break
      ;;
  esac
done

sel_file="${1:-}"
shift || true

# Flags may also trail the selection path (dispatch_async.sh appends extras
# after the snapshot), so scan what's left of the args for them too.
for _arg in "$@"; do
  case "$_arg" in
    --force) force_remove=1 ;;
    --check) check_only=1 ;;
  esac
done

if [ -z "$sel_file" ] || [ ! -f "$sel_file" ]; then
  exit 0
fi

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/herdr-pickers"
cache_file="${cache_dir}/pick_session_items.tsv"
pending_file="${cache_dir}/pick_session_pending.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"
rm_log_file="${cache_dir}/pick_session_remove_worktrees.log"
rm_log_max_lines=2000
mkdir -p "$cache_dir"

realpath_or_self() {
  realpath "$1" 2> /dev/null || printf '%s' "$1"
}

# shellcheck source=../lib/herdr_ws.sh
. "$HOME/.config/herdr/scripts/pickers/lib/herdr_ws.sh"

current_session=""
if [ -n "${HERDR_SOCKET_PATH:-}" ]; then
  current_session="$(hws_current)"
fi

list_worktree_paths() {
  local root="$1"
  [ -n "$root" ] || return 1
  git -C "$root" worktree list --porcelain 2> /dev/null | sed -n 's/^worktree //p' | sed '/^$/d' || true
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

# Close workspaces registered at any of the paths, by id. The current
# workspace survives unless the user selected it.
close_workspaces_for_paths() {
  local cur_sess="$1"
  shift || true
  local -a paths=("$@")

  [ -n "${HERDR_SOCKET_PATH:-}" ] || return 0
  [ ${#paths[@]} -gt 0 ] || return 0

  local sname spath ws_id rspath p rp
  while IFS=$'\t' read -r sname spath ws_id; do
    [ -n "$sname" ] && [ -n "$spath" ] && [ -n "$ws_id" ] || continue
    if [ -n "$cur_sess" ] && [ "$sname" = "$cur_sess" ] && [ -z "${explicit_sessions_set["$sname"]+x}" ]; then
      continue
    fi
    rspath="$(realpath_or_self "$spath")"
    for p in "${paths[@]}"; do
      [ -n "$p" ] || continue
      rp="$(realpath_or_self "$p")"
      if [ "$rspath" = "$rp" ]; then
        hws_close_id "$ws_id" || true
        break
      fi
    done
  done < <(hws_list_registered)
}

remove_paths_in_background() {
  local root="$1"
  shift
  local -a paths=("$@")
  [ ${#paths[@]} -gt 0 ] || return 0

  if ! command -v ,w > /dev/null 2>&1; then
    picker_notify "session picker: missing command: ,w"
    return 0
  fi

  # Detach removal work from the picker UI:
  # - Close matching workspaces ourselves (protecting the current workspace
  #   unless it was explicitly selected); COMMA_W_KEEP_WORKSPACES stops
  #   `,w remove` from closing the current workspace by path.
  local cmd
  cmd="cd $(printf %q "$root") && ,w remove"
  if [ "$force_remove" -eq 1 ]; then
    cmd+=" --force"
  fi
  cmd+=" --paths"
  local p
  for p in "${paths[@]}"; do
    cmd+=" $(printf %q "$p")"
  done
  {
    printf '\n[%s] %s\n' "$(date +%Y-%m-%dT%H:%M:%S%z)" "$cmd"
  } >> "$rm_log_file" 2> /dev/null || true

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

  close_workspaces_for_paths "$current_session" "${paths[@]}" || true
  "$HOME/lib/shared/detach.sh" env COMMA_W_KEEP_WORKSPACES=1 bash -c "$cmd" < /dev/null >> "$rm_log_file" 2>&1 &
}

declare -A roots_selected=()
declare -A worktree_paths_by_root=()
declare -a pending_wt_paths=()
declare -a pending_plain_dirs=()
declare -a explicit_sessions=()
declare -A explicit_sessions_set=()

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
      # Stale linked worktree: the directory still exists on disk but its git
      # linkage is broken (the `.git` file points at a `worktrees/<name>` admin
      # dir that's gone). The indexer can't resolve a root checkout for these,
      # so it emits them with `wt_root:` meta and target == path, which would
      # route them to `remove_all_worktrees.sh` — which bails on its
      # `rev-parse --is-inside-work-tree` guard and leaves the dir untouched.
      # Such a dir is an orphan (its owning repo already dropped the admin
      # files), so the complete fix is a safe `rm -rf`. Route it to the
      # plain-dir remover, matching the prefix the optimistic hide already
      # tombstones for this row.
      if [ -d "$wt_path" ] && ! git -C "$wt_path" rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        pending_plain_dirs+=("$wt_path")
        continue
      fi
      root_wt_dir="$target"
      case "$meta_base" in
        wt_root:*) is_root_selection=1 ;;
      esac
      ;;
    session)
      if [ -n "${target:-}" ]; then
        explicit_sessions+=("$target")
        explicit_sessions_set["$target"]=1
      fi
      wt_path="$(worktree_dir_for_path "$path" 2> /dev/null || true)"
      if [ -z "$wt_path" ] && [ -n "${target:-}" ] && [ -f "$cache_file" ]; then
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

      # Same stale-worktree guard as the `worktree` kind above. A session can be
      # backed by a stale linked worktree (its `.git` file points at a missing
      # `worktrees/<name>` admin dir). The indexer puts such an orphan in its own
      # single-member group whose root_checkout *is* the orphan dir, so the row is
      # tagged `sess_root:`. `worktree_root_dir_for_path` then resolves the root
      # purely from the `.git` file *text* — yielding the real, live root checkout
      # (e.g. `kibana/main`) regardless of the broken linkage. Combined with
      # `sess_root:` that makes `is_root_selection=1`, which would dispatch
      # `remove_all_worktrees.sh <live-root>` and `rm -rf` the entire repo wrapper.
      # Detect the broken linkage and route just the orphan dir to the plain-dir
      # remover (safe `rm -rf` under $HOME), matching the optimistic-hide prefix.
      if [ -d "$wt_path" ] && ! git -C "$wt_path" rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        pending_plain_dirs+=("$wt_path")
        continue
      fi

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
  if [ -n "${HERDR_SOCKET_PATH:-}" ]; then
    picker_notify "pick_session: selection contains nothing to remove"
  fi
  exit 0
fi

if [ ${#pending_wt_paths[@]} -gt 0 ]; then
  mapfile -t pending_wt_paths < <(printf '%s\n' "${pending_wt_paths[@]}" | sed '/^$/d' | LC_ALL=C sort -u)
fi

# Check-only mode (picker's alt-x transform): resolve selections exactly like
# a real run, then report the preflight verdict with zero side effects.
# Exit 0 = safe to remove without force; exit 3 = blocked by removal safety checks.
# Plain directories have no git safety state, so their recursive delete always needs Force.
if [ "$check_only" -eq 1 ]; then
  [ "$force_remove" -eq 1 ] && exit 0
  [ ${#pending_plain_dirs[@]} -eq 0 ] || exit 3
  [ ${#pending_wt_paths[@]} -gt 0 ] || exit 0
  command -v ,w > /dev/null 2>&1 || exit 3
  _preflight="$(,w remove --preflight --paths "${pending_wt_paths[@]}" 2> /dev/null)" || exit 3
  _check_blocked=0
  while IFS= read -r _p; do
    [ -n "$_p" ] || continue
    _check_blocked=1
    break
  done <<< "$_preflight"
  if [ "$_check_blocked" -eq 1 ]; then
    exit 3
  fi
  exit 0
fi

# Preflight worktree removal safety BEFORE
# any destructive step below: session kills, pending/tombstone writes, and the
# backgrounded `,w remove` all assume the removal will happen. Non-forced runs
# are gated by the picker's alt-x `--check` first; reaching this gate blocked
# means state changed since that check, so abort cleanly instead of forcing.
declare -A unsafe_wt=()
if [ "$force_remove" -eq 0 ] && [ ${#pending_plain_dirs[@]} -gt 0 ]; then
  picker_notify "pick_session: deleting a plain directory needs Force; press alt-x again"
  exit 0
fi
if [ "$force_remove" -eq 0 ] && [ ${#pending_wt_paths[@]} -gt 0 ] && ! command -v ,w > /dev/null 2>&1; then
  exit 3
fi
if [ "$force_remove" -eq 0 ] && [ ${#pending_wt_paths[@]} -gt 0 ] && command -v ,w > /dev/null 2>&1; then
  _preflight="$(,w remove --preflight --paths "${pending_wt_paths[@]}" 2> /dev/null)" || exit 3
  while IFS= read -r _p; do
    [ -n "$_p" ] || continue
    unsafe_wt["$_p"]=1
  done <<< "$_preflight"
  if [ ${#unsafe_wt[@]} -gt 0 ]; then
    picker_notify "pick_session: blocked by work or submodule safety checks; press alt-x again to force"
    exit 0
  fi
fi
{
  for p in "${pending_wt_paths[@]}"; do
    printf 'WT\t%s\n' "$p"
  done
  for p in "${pending_plain_dirs[@]}"; do
    printf 'DIR\t%s\n' "$p"
  done
} | python3 "$script_dir/../lib/resource_lock.py" remove-mark "$pending_file" "$mutation_file"

if [ -n "${HERDR_SOCKET_PATH:-}" ]; then
  pick_session_scan_roots_raw="$(picker_opt '@pick_session_worktree_scan_roots' "$HOME/code,$HOME/.local/share")"

  # Selected workspace rows close by exact label; path matching below covers
  # unselected workspaces registered at removed worktree paths.
  for s in "${explicit_sessions[@]+"${explicit_sessions[@]}"}"; do
    hws_close "$s" || true
  done

  for root in "${!roots_selected[@]}"; do
    "$HOME/lib/shared/detach.sh" env COMMA_W_KEEP_WORKSPACES=1 PICK_SESSION_CURRENT_SESSION="$current_session" PICK_SESSION_SCAN_ROOTS="$pick_session_scan_roots_raw" "$HOME/.config/herdr/scripts/pickers/session/remove_all_worktrees.sh" "$root" "$force_remove" < /dev/null > /dev/null 2>&1 &
  done

  for root in "${!worktree_paths_by_root[@]}"; do
    if [ -n "${roots_selected["$root"]+x}" ]; then
      continue
    fi
    mapfile -t paths < <(printf '%s\n' "${worktree_paths_by_root[$root]}" | sed '/^$/d' | sort -u)
    # Drop paths the preflight above marked unsafe (keys are realpath'd the
    # same way both lists were built, via realpath_or_self).
    declare -a _dispatch_paths=()
    for p in "${paths[@]}"; do
      [ -n "${unsafe_wt[$p]+x}" ] || _dispatch_paths+=("$p")
    done
    paths=(${_dispatch_paths[@]+"${_dispatch_paths[@]}"})
    if [ ${#paths[@]} -gt 0 ]; then
      remove_paths_in_background "$root" "${paths[@]}"
    fi
  done

  if [ ${#pending_plain_dirs[@]} -gt 0 ]; then
    for i in "${!pending_plain_dirs[@]}"; do
      pd="${pending_plain_dirs[$i]}"
      "$HOME/lib/shared/detach.sh" env COMMA_W_KEEP_WORKSPACES=1 "$HOME/.config/herdr/scripts/pickers/session/remove_plain_dir.sh" "$pd" "$HOME" < /dev/null > /dev/null 2>&1 &
    done
  fi
fi

if [ ${#pending_plain_dirs[@]} -gt 0 ] && command -v zoxide > /dev/null 2>&1; then
  for pd in "${pending_plain_dirs[@]}"; do
    zoxide remove "$pd" 2> /dev/null || true
  done
fi

if [ -f "$cache_file" ]; then
  CACHE_FILE="$cache_file" PENDING_WT="$(printf '%s\n' "${pending_wt_paths[@]-}")" PENDING_DIRS="$(printf '%s\n' "${pending_plain_dirs[@]-}")" python3 "$script_dir/../lib/resource_lock.py" --timeout 0.2 cache-run "$cache_file" python3 "$script_dir/lib/cache_prune_paths.py" || true
fi
