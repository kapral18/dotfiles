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

root_wt_dir="${1:-}"
force_remove="${2:-0}"
if [ -z "$root_wt_dir" ]; then
  exit 0
fi

realpath_or_self() {
  realpath "$1" 2> /dev/null || printf '%s' "$1"
}

notify_tmux() {
  local msg="$1"
  # Only notify when running inside a tmux client. When this is launched from
  # the picker we intentionally unset TMUX to avoid stealing popup focus.
  if [ -n "${TMUX:-}" ] && command -v tmux > /dev/null 2>&1; then
    tmux display-message -d 6000 "$msg" 2> /dev/null || true
  fi
}

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

  local path="$url"
  case "$url" in
    *://*)
      path="${url##*/}"
      ;;
    *:*)
      path="${url#*:}"
      path="${path##*/}"
      ;;
    *)
      path="${url##*/}"
      ;;
  esac
  [ -n "$path" ] || return 1
  printf '%s\n' "$path"
}

# Deletion allowlist: only remove a resolved target that is a STRICT descendant
# of an approved root (HOME plus each PICK_SESSION_SCAN_ROOTS entry). Refuse the
# roots and ancestors containing them before allowing any descendant, plus "",
# "/", paths outside every root, and symlinks that resolve outside.
approved_roots=()
add_approved_root() {
  local r="$1"
  [ -n "$r" ] || return 0
  # shellcheck disable=SC2088  # literal "~/" is matched, then expanded by hand
  case "$r" in
    "~") r="${HOME:-}" ;;
    "~/"*) r="${HOME:-}/${r#\~/}" ;;
  esac
  [ -n "$r" ] || return 0
  r="$(realpath_or_self "$r")"
  case "$r" in
    "" | "/") return 0 ;;
  esac
  approved_roots+=("$r")
}

if [ -n "${HOME:-}" ]; then
  add_approved_root "$HOME"
fi
if [ -n "${PICK_SESSION_SCAN_ROOTS:-}" ]; then
  _old_ifs="$IFS"
  IFS=','
  for _scan_root in $PICK_SESSION_SCAN_ROOTS; do
    _scan_root="${_scan_root#"${_scan_root%%[![:space:]]*}"}"
    _scan_root="${_scan_root%"${_scan_root##*[![:space:]]}"}"
    add_approved_root "$_scan_root"
  done
  IFS="$_old_ifs"
  unset _old_ifs _scan_root
fi

target_is_approved_deletion() {
  local target="$1"
  case "$target" in
    "" | "/") return 1 ;;
  esac
  [ "${#approved_roots[@]}" -gt 0 ] || return 1
  local r
  for r in "${approved_roots[@]}"; do
    case "$r" in
      "$target" | "$target"/*) return 1 ;;
    esac
  done
  for r in "${approved_roots[@]}"; do
    [ -n "$r" ] || continue
    case "$target" in
      "$r"/*) return 0 ;;
    esac
  done
  return 1
}

safe_rm_rf() {
  local target
  target="$(realpath_or_self "$1")"
  if ! target_is_approved_deletion "$target"; then
    return 1
  fi
  rm -rf "$target"
}

safe_rmdir() {
  local target
  target="$(realpath_or_self "$1")"
  target_is_approved_deletion "$target" || return 1
  rmdir "$target"
}

cd "$root_wt_dir" 2> /dev/null || exit 0
root="$(pwd -P)"

if ! git -C "$root" rev-parse --is-inside-work-tree > /dev/null 2>&1; then
  exit 0
fi
target_is_approved_deletion "$root" || exit 0

current_session="${PICK_SESSION_CURRENT_SESSION:-}"
if [ -z "$current_session" ] && [ -n "${TMUX:-}" ] && command -v tmux > /dev/null 2>&1; then
  current_session="$(tmux display-message -p '#S' 2> /dev/null || true)"
fi

mapfile -t worktrees < <(git -C "$root" worktree list --porcelain 2> /dev/null | sed -n 's/^worktree //p' | sed '/^$/d' || true)
if [ ${#worktrees[@]} -eq 0 ]; then
  exit 0
fi

[ "$(realpath_or_self "${worktrees[0]}")" = "$root" ] || exit 3
if [ "$force_remove" != "1" ]; then
  python3 "$HOME/lib/shared/worktree_nested_git.py" "$root" --all-worktrees || exit 3
  checkout_heads=()
  for wt in "${worktrees[@]}"; do
    checkout_head="$(git -C "$wt" rev-parse --verify HEAD 2> /dev/null)" || exit 3
    checkout_heads+=("$checkout_head")
    target_is_approved_deletion "$(realpath_or_self "$wt")" || continue
    top="$(git -C "$wt" rev-parse --show-toplevel 2> /dev/null)" || exit 3
    [ "$(realpath_or_self "$wt")" = "$(realpath_or_self "$top")" ] || exit 3
    dirty="$(git -C "$wt" status --porcelain -unormal 2> /dev/null)" || exit 3
    [ -z "$dirty" ] || exit 3
  done
  unsafe_commits="$(git -C "$root" rev-list --all "${checkout_heads[@]}" --not --remotes 2> /dev/null)" || exit 3
  [ -z "$unsafe_commits" ] || exit 3
fi

repo_name="$(repo_name_from_remote "$root" 2> /dev/null || true)"
wrapper="$(dirname "$root")"
wrapper="$(realpath_or_self "$wrapper")"

should_nuke_wrapper=0
if [ -n "$repo_name" ] && [ "$(basename "$wrapper")" = "$repo_name" ] && target_is_approved_deletion "$wrapper"; then
  should_nuke_wrapper=1
fi

nuke_dir="$root"
if [ "$should_nuke_wrapper" -eq 1 ]; then
  nuke_dir="$wrapper"
fi

notify_tmux "pick_session: removing repo at $nuke_dir"

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
pending_file="${cache_dir}/pick_session_pending.tsv"

dir_is_effectively_empty_ignoring_ds_store() {
  local dir="$1"
  [ -n "$dir" ] || return 1
  [ -d "$dir" ] || return 1
  rm -f "$dir/.DS_Store" 2> /dev/null || true
  [ -z "$(find "$dir" -mindepth 1 -maxdepth 1 ! -name '.DS_Store' -print -quit 2> /dev/null || true)" ]
}

remove_selected_worktrees() {
  local wt
  for wt in "${worktrees[@]}"; do
    wt="$(realpath_or_self "$wt")"
    [ -n "$wt" ] || continue
    case "$wt" in
      */.git/* | */.git) continue ;;
    esac
    safe_rm_rf "$wt" || true
  done
}

cleanup_pending_entries() {
  python3 "$script_dir/../lib/resource_lock.py" pending-prune "$pending_file" "$@"
}

kill_sessions_under_prefixes() {
  command -v tmux > /dev/null 2>&1 || return 0

  local -a prefixes_raw=("$@")
  [ ${#prefixes_raw[@]} -gt 0 ] || return 0

  local -a prefixes=()
  local pref
  for pref in "${prefixes_raw[@]}"; do
    [ -n "$pref" ] || continue
    pref="$(realpath_or_self "$pref")"
    [ -n "$pref" ] || continue
    prefixes+=("$pref")
  done
  [ ${#prefixes[@]} -gt 0 ] || return 0

  local -a to_kill=()
  local sname spath rspath
  while IFS=$'\t' read -r sname spath; do
    [ -n "$sname" ] || continue
    [ -n "$spath" ] || continue
    rspath="$(realpath_or_self "$spath")"
    for pref in "${prefixes[@]}"; do
      case "$rspath" in
        "$pref" | "$pref"/*)
          to_kill+=("$sname")
          break
          ;;
      esac
    done
  done < <(tmux list-sessions -F $'#{session_name}\t#{session_path}' 2> /dev/null || true)

  if [ ${#to_kill[@]} -eq 0 ]; then
    return 0
  fi

  mapfile -t to_kill < <(printf '%s\n' "${to_kill[@]}" | sed '/^$/d' | LC_ALL=C sort -u)

  local s
  for s in "${to_kill[@]}"; do
    [ -n "$s" ] || continue
    # Never kill the initiating/current session from an async picker action.
    # This avoids "alt-x on sibling worktree" tearing down the active session.
    [ -n "${current_session:-}" ] && [ "$s" = "${current_session:-}" ] && continue
    tmux kill-session -t "=$s" 2> /dev/null || true
  done
}

kill_prefixes=("$nuke_dir")
wt=""
for wt in "${worktrees[@]}"; do
  wt="$(realpath_or_self "$wt")"
  [ -n "$wt" ] || continue
  kill_prefixes+=("$wt")
done
mapfile -t kill_prefixes < <(printf '%s\n' "${kill_prefixes[@]}" | sed '/^$/d' | LC_ALL=C sort -u)
kill_sessions_under_prefixes "${kill_prefixes[@]}"

pending_cleanup_paths=("$nuke_dir")
pending_cleanup_paths+=("$wrapper")
wt=""
for wt in "${worktrees[@]}"; do
  wt="$(realpath_or_self "$wt")"
  [ -n "$wt" ] || continue
  pending_cleanup_paths+=("$wt")
done

wt=""
for wt in "${worktrees[@]}"; do
  wt="$(realpath_or_self "$wt")"
  [ -n "$wt" ] || continue
  case "$wt" in
    */.git/* | */.git) continue ;;
  esac
  case "$wt" in
    "$nuke_dir" | "$nuke_dir"/*) ;;
    *)
      safe_rm_rf "$wt" || true
      ;;
  esac
done

if [ "$should_nuke_wrapper" -eq 1 ]; then
  ts="$(date +%Y%m%d-%H%M%S)"
  bag_root="$(dirname "$wrapper")/.bag/pickers/session/$(basename "$wrapper")/$ts"
  bag_status="$(mktemp -t pick_session_bag_status.XXXXXX)"
  trap 'rm -f "$bag_status" 2> /dev/null || true' EXIT

  mapfile -t wt_rels < <(
    printf '%s\n' "${worktrees[@]}" \
      | while IFS= read -r p; do
        p="$(realpath_or_self "$p")"
        prefix="${wrapper}/"
        if [[ "$p" == "$prefix"* ]]; then
          printf '%s\n' "${p:${#prefix}}"
        fi
      done \
      | sed '/^$/d' \
      | LC_ALL=C sort -u
  )

  moved_count="$(
    BAG_PRESERVE_STATUS_FILE="$bag_status" WRAPPER="$wrapper" BAG_ROOT="$bag_root" WT_RELS="$(printf '%s\n' "${wt_rels[@]}")" python3 "$script_dir/lib/bag_preserve_non_wt.py"
  )"

  case "${moved_count:-0}" in
    '' | *[!0-9]*) moved_count=0 ;;
  esac
  blocked_by_unselected_git_root=0
  if grep -q '^blocked_by_unselected_git_root=1$' "$bag_status" 2> /dev/null; then
    blocked_by_unselected_git_root=1
  fi

  if [ "$blocked_by_unselected_git_root" -eq 1 ]; then
    notify_tmux "pick_session: kept non-worktree content in $wrapper because it contains another git repo"
  elif [ "$moved_count" -gt 0 ]; then
    notify_tmux "pick_session: preserved $moved_count non-worktree item(s) to $bag_root"
  else
    # Another removal can share this timestamp; zero moves do not imply ownership.
    if [ -d "$bag_root" ]; then
      safe_rmdir "$bag_root" 2> /dev/null || true
      cur="$(dirname "$bag_root")"
      stop="$(dirname "$wrapper")/.bag"
      while [ -n "$cur" ] && [ "$cur" != "/" ] && [ "$cur" != "$stop" ]; do
        if ! dir_is_effectively_empty_ignoring_ds_store "$cur"; then
          break
        fi
        safe_rmdir "$cur" 2> /dev/null || break
        cur="$(dirname "$cur")"
      done
    fi
  fi

  remove_selected_worktrees

  # If nothing needed preserving, don't leave empty bag dirs. `.DS_Store` does
  # not count as content.
  if [ -d "$bag_root" ] && dir_is_effectively_empty_ignoring_ds_store "$bag_root"; then
    safe_rmdir "$bag_root" 2> /dev/null || true
    cur="$(dirname "$bag_root")"
    stop="$(dirname "$wrapper")/.bag"
    while [ -n "$cur" ] && [ "$cur" != "/" ] && [ "$cur" != "$stop" ]; do
      if ! dir_is_effectively_empty_ignoring_ds_store "$cur"; then
        break
      fi
      safe_rmdir "$cur" 2> /dev/null || break
      cur="$(dirname "$cur")"
    done
  fi

  if dir_is_effectively_empty_ignoring_ds_store "$wrapper" && safe_rmdir "$wrapper"; then
    notify_tmux "pick_session: removed $wrapper"
  else
    notify_tmux "pick_session: kept $wrapper"
  fi
  cleanup_pending_entries "${pending_cleanup_paths[@]}"
  if command -v tmux > /dev/null 2>&1; then
    # Run directly; avoid `tmux run-shell` which can steal focus from popups.
    nohup "$HOME/.config/tmux/scripts/pickers/session/index_update.sh" --force --quiet < /dev/null > /dev/null 2>&1 &
  fi
  exit 0
fi

safe_rm_rf "$nuke_dir" || exit 0
notify_tmux "pick_session: removed $nuke_dir"

# If the wrapper dir wasn't considered "canonical" (repo-name match) we won't
# delete it outright, but if it becomes empty (ignoring `.DS_Store`) after
# deleting all worktrees, delete it too.
if [ "$should_nuke_wrapper" -ne 1 ] && [ -d "$wrapper" ]; then
  wrapper_rp="$(realpath_or_self "$wrapper")"
  if target_is_approved_deletion "$wrapper_rp" && dir_is_effectively_empty_ignoring_ds_store "$wrapper_rp" && safe_rmdir "$wrapper_rp"; then
    notify_tmux "pick_session: removed empty wrapper $wrapper_rp"
  fi
fi

cleanup_pending_entries "${pending_cleanup_paths[@]}"
if command -v tmux > /dev/null 2>&1; then
  nohup "$HOME/.config/tmux/scripts/pickers/session/index_update.sh" --force --quiet < /dev/null > /dev/null 2>&1 &
fi
