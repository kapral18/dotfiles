#!/usr/bin/env bash
set -euo pipefail

root_wt_dir="${1:-}"
if [ -z "$root_wt_dir" ]; then
  exit 0
fi

realpath_or_self() {
  realpath "$1" 2>/dev/null || printf '%s' "$1"
}

notify_tmux() {
  local msg="$1"
  # Only notify when running inside a tmux client. When this is launched from
  # the picker we intentionally unset TMUX to avoid stealing popup focus.
  if [ -n "${TMUX:-}" ] && command -v tmux >/dev/null 2>&1; then
    tmux display-message -d 6000 "$msg" 2>/dev/null || true
  fi
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

safe_rm_rf() {
  local target="$1"
  target="$(realpath_or_self "$target")"
  case "$target" in
  "" | "/") return 1 ;;
  esac
  if [ -n "${HOME:-}" ] && [ "$target" = "$(realpath_or_self "$HOME")" ]; then
    return 1
  fi
  rm -rf "$target"
}

cd "$root_wt_dir" 2>/dev/null || exit 0
root="$(pwd -P)"

if ! git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

current_session=""
if [ -n "${TMUX:-}" ] && command -v tmux >/dev/null 2>&1; then
  current_session="$(tmux display-message -p '#S' 2>/dev/null || true)"
fi

mapfile -t worktrees < <(git -C "$root" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2}' | sed '/^$/d' || true)
if [ ${#worktrees[@]} -eq 0 ]; then
  exit 0
fi

repo_name="$(repo_name_from_remote "$root" 2>/dev/null || true)"
wrapper="$(dirname "$root")"
wrapper="$(realpath_or_self "$wrapper")"

should_nuke_wrapper=0
if [ -n "$repo_name" ] && [ "$(basename "$wrapper")" = "$repo_name" ]; then
  case "$wrapper" in
  "" | "/") should_nuke_wrapper=0 ;;
  *)
    if [ -n "${HOME:-}" ] && [ "$wrapper" = "$(realpath_or_self "$HOME")" ]; then
      should_nuke_wrapper=0
    else
      should_nuke_wrapper=1
    fi
    ;;
  esac
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
  rm -f "$dir/.DS_Store" 2>/dev/null || true
  [ -z "$(find "$dir" -mindepth 1 -maxdepth 1 ! -name '.DS_Store' -print -quit 2>/dev/null || true)" ]
}

cleanup_pending_entries() {
  [ -f "$pending_file" ] || return 0
  local tmp
  tmp="$(mktemp -t pick_session_pending.XXXXXX)"
  cp "$pending_file" "$tmp"
  local p rp
  for p in "$@"; do
    [ -n "$p" ] || continue
    rp="$(realpath_or_self "$p")"
    if [ ! -e "$rp" ]; then
      grep -v -F $'WT\t'"$rp" "$tmp" >"${tmp}.2" || true
      mv -f "${tmp}.2" "$tmp"
    fi
  done
  mv -f "$tmp" "$pending_file"
}

kill_sessions_under_prefixes() {
  command -v tmux >/dev/null 2>&1 || return 0

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
  done < <(tmux list-sessions -F $'#{session_name}\t#{session_path}' 2>/dev/null || true)

  if [ ${#to_kill[@]} -eq 0 ]; then
    return 0
  fi

  mapfile -t to_kill < <(printf '%s\n' "${to_kill[@]}" | sed '/^$/d' | LC_ALL=C sort -u)

  local s
  for s in "${to_kill[@]}"; do
    [ -n "$s" ] || continue
    [ "$s" = "${current_session:-}" ] && continue
    tmux kill-session -t "$s" 2>/dev/null || true
  done
  for s in "${to_kill[@]}"; do
    [ -n "$s" ] || continue
    [ "$s" != "${current_session:-}" ] && continue
    tmux kill-session -t "$s" 2>/dev/null || true
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
    # Worktrees outside the wrapper/root still need cleanup.
    safe_rm_rf "$wt" || true
    ;;
  esac
done

if [ "$should_nuke_wrapper" -eq 1 ]; then
  # Preserve any non-worktree files/dirs that live anywhere under the wrapper,
  # then nuke the wrapper in one shot. `.DS_Store` is ignored.
  ts="$(date +%Y%m%d-%H%M%S)"
  bag_root="$(dirname "$wrapper")/.bag/pick_session/$(basename "$wrapper")/$ts"

  mapfile -t wt_rels < <(
    printf '%s\n' "${worktrees[@]}" |
      while IFS= read -r p; do
        p="$(realpath_or_self "$p")"
        case "$p" in
        "$wrapper"/*) printf '%s\n' "${p#"$wrapper"/}" ;;
        esac
      done |
      sed '/^$/d' |
      LC_ALL=C sort -u
  )

  moved_count="$(
    WRAPPER="$wrapper" BAG_ROOT="$bag_root" WT_RELS="$(printf '%s\n' "${wt_rels[@]}")" python3 - <<'PY'
import os
import shutil
from pathlib import Path

wrapper = Path(os.environ["WRAPPER"]).resolve()
bag_root = Path(os.environ["BAG_ROOT"]).resolve()
wt_rels_raw = os.environ.get("WT_RELS", "")

worktree_roots = set()
protected_dirs = set()
for rel in wt_rels_raw.splitlines():
    rel = rel.strip().strip("/")
    if not rel:
        continue
    root = (wrapper / rel).resolve()
    worktree_roots.add(root)
    cur = root
    while True:
        protected_dirs.add(cur)
        if cur == wrapper:
            break
        if cur.parent == cur:
            break
        cur = cur.parent
protected_dirs.add(wrapper)

def is_worktree_root(p: Path) -> bool:
    try:
        rp = p.resolve()
    except Exception:
        rp = p
    return rp in worktree_roots

def is_protected_dir(p: Path) -> bool:
    try:
        rp = p.resolve()
    except Exception:
        rp = p
    return rp in protected_dirs

def rel_to_wrapper(p: Path) -> Path:
    try:
        return p.resolve().relative_to(wrapper)
    except Exception:
        try:
            return p.relative_to(wrapper)
        except Exception:
            return Path("")

def move_to_bag(src: Path):
    rel = rel_to_wrapper(src)
    if not rel or str(rel) == ".":
        return
    dest = bag_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(src), str(dest))
        return True
    except Exception:
        return False

moved = 0

for root, dirs, files in os.walk(wrapper, topdown=True, followlinks=False):
    rootp = Path(root)
    if is_worktree_root(rootp):
        dirs[:] = []
        continue

    next_dirs = []
    for d in dirs:
        child = rootp / d
        if is_worktree_root(child):
            continue
        if child.is_symlink():
            moved += 1 if move_to_bag(child) else 0
            continue
        if not is_protected_dir(child):
            moved += 1 if move_to_bag(child) else 0
            continue
        next_dirs.append(d)
    dirs[:] = next_dirs

    for f in files:
        if f == ".DS_Store":
            try:
                (rootp / f).unlink()
            except Exception:
                pass
            continue
        moved += 1 if move_to_bag(rootp / f) else 0

print(moved)
PY
  )"

  case "${moved_count:-0}" in
  '' | *[!0-9]*) moved_count=0 ;;
  esac
  if [ "$moved_count" -gt 0 ]; then
    notify_tmux "pick_session: preserved $moved_count non-worktree item(s) to $bag_root"
  else
    # If the preservation step created an empty bag dir (e.g. due to a failed
    # move), remove it so we don't leave noisy empty timestamps behind.
    if [ -d "$bag_root" ]; then
      safe_rm_rf "$bag_root" || true
      cur="$(dirname "$bag_root")"
      stop="$(dirname "$wrapper")/.bag"
      while [ -n "$cur" ] && [ "$cur" != "/" ] && [ "$cur" != "$stop" ]; do
        if ! dir_is_effectively_empty_ignoring_ds_store "$cur"; then
          break
        fi
        rmdir "$cur" 2>/dev/null || break
        cur="$(dirname "$cur")"
      done
    fi
  fi

  # If nothing needed preserving, don't leave empty bag dirs. `.DS_Store` does
  # not count as content.
  if [ -d "$bag_root" ] && dir_is_effectively_empty_ignoring_ds_store "$bag_root"; then
    rmdir "$bag_root" 2>/dev/null || true
    cur="$(dirname "$bag_root")"
    stop="$(dirname "$wrapper")/.bag"
    while [ -n "$cur" ] && [ "$cur" != "/" ] && [ "$cur" != "$stop" ]; do
      if ! dir_is_effectively_empty_ignoring_ds_store "$cur"; then
        break
      fi
      rmdir "$cur" 2>/dev/null || break
      cur="$(dirname "$cur")"
    done
  fi

  safe_rm_rf "$wrapper" || exit 0
  notify_tmux "pick_session: removed $wrapper"
  cleanup_pending_entries "${pending_cleanup_paths[@]}"
  if command -v tmux >/dev/null 2>&1; then
    # Run directly; avoid `tmux run-shell` which can steal focus from popups.
    nohup "$HOME/.config/tmux/scripts/pick_session_index_update.sh" --force --quiet </dev/null >/dev/null 2>&1 &
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
  case "$wrapper_rp" in
  "" | "/") ;;
  *)
    if [ -n "${HOME:-}" ] && [ "$wrapper_rp" = "$(realpath_or_self "$HOME")" ]; then
      :
    elif dir_is_effectively_empty_ignoring_ds_store "$wrapper_rp"; then
      rmdir "$wrapper_rp" 2>/dev/null || safe_rm_rf "$wrapper_rp" || true
      notify_tmux "pick_session: removed empty wrapper $wrapper_rp"
    fi
    ;;
  esac
fi

cleanup_pending_entries "${pending_cleanup_paths[@]}"
if command -v tmux >/dev/null 2>&1; then
  nohup "$HOME/.config/tmux/scripts/pick_session_index_update.sh" --force --quiet </dev/null >/dev/null 2>&1 &
fi
