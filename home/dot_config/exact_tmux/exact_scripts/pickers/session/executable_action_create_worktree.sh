#!/usr/bin/env bash
# alt-c worktree-create action: create a new worktree off the repo behind the
# selected picker row, using ,w add. Invoked from pick_session.sh's enter
# transform while in worktree-create mode.
#
#   action_create_worktree.sh <selection_snapshot> <branch_name_file>
#
# `sel_file` is a per-binding mktemp snapshot minted by dispatch_async.sh at
# enter-time; `branch_file` holds the typed branch name ({q}). We own cleanup
# of both, same as action_send_command.sh.
if [ "${BASH_VERSINFO[0]:-0}" -lt 4 ]; then
  for _b in /opt/homebrew/bin/bash /usr/local/bin/bash; do
    [ -x "$_b" ] && exec "$_b" "$0" "$@"
  done
  exit 1
fi
set -euo pipefail

sel_file="${1:-}"
branch_file="${2:-}"

[ -n "$sel_file" ] && [ -f "$sel_file" ] || exit 0
[ -n "$branch_file" ] && [ -f "$branch_file" ] || exit 0

trap 'rm -f "$sel_file" "$branch_file" 2>/dev/null || true' EXIT

branch="$(cat "$branch_file" 2> /dev/null || true)"
# Trim surrounding whitespace.
branch="${branch#"${branch%%[![:space:]]*}"}"
branch="${branch%"${branch##*[![:space:]]}"}"
[ -n "$branch" ] || exit 0

# Shared helpers: resolve_path, worktree_root_dir_for_path.
# shellcheck source=lib/session_naming.sh
# shellcheck disable=SC1091
. "$HOME/.config/tmux/scripts/pickers/session/lib/session_naming.sh"

notify() {
  command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ] || return 0
  tmux display-message -d 3000 "pick_session: $1" 2> /dev/null || true
}

# Read the first selected row; worktree creation acts on a single repo.
line="$(head -n 1 "$sel_file" 2> /dev/null || true)"
[ -n "$line" ] || exit 0
IFS=$'\t' read -r _disp kind path _meta target _mk <<< "$line"

[ -n "$path" ] || exit 0

# Resolve the repo root checkout that owns the selected row. For worktree/dir
# rows the worktree root walk finds the enclosing .git; the cache's target is
# the root checkout for worktree/session rows when present.
repo_root=""
case "$kind" in
  worktree | session)
    repo_root="$target"
    ;;
esac
if [ -z "$repo_root" ] || [ ! -d "$repo_root" ]; then
  repo_root="$(worktree_root_dir_for_path "$path" 2> /dev/null || true)"
fi
[ -n "$repo_root" ] || repo_root="$path"
repo_root="$(resolve_path "$repo_root" 2> /dev/null || printf '%s' "$repo_root")"

if [ ! -d "$repo_root" ] || ! git -C "$repo_root" rev-parse --is-inside-work-tree > /dev/null 2>&1; then
  notify "alt-c: selected row is not inside a git repo"
  exit 0
fi

# ,w lives in ~/bin; resolve it explicitly since the picker's PATH under
# /bin/sh popups may not include it.
w_cmd=""
for _c in ",w" "$HOME/bin/,w"; do
  if command -v "$_c" > /dev/null 2>&1; then
    w_cmd="$(command -v "$_c")"
    break
  fi
  [ -x "$_c" ] && w_cmd="$_c" && break
done
if [ -z "$w_cmd" ]; then
  notify "alt-c: ,w not found on PATH"
  exit 0
fi

# ,w add creates the worktree and its tmux session (via _add_worktree_tmux_session).
# Run with cwd at the repo root so ,w infers the right parent dir.
if (cd "$repo_root" && "$w_cmd" add -q "$branch") > /dev/null 2>&1; then
  notify "created worktree: $branch"
else
  notify "alt-c: failed to create worktree '$branch'"
  exit 0
fi

# Reindex + reload so the new worktree/session appears without a manual ctrl-r.
update_cmd="$HOME/.config/tmux/scripts/pickers/session/index_update.sh"
[ -x "$update_cmd" ] && "$update_cmd" --force --quiet --quick-only > /dev/null 2>&1 || true

fzf_reload_cmd="$HOME/.config/tmux/scripts/pickers/session/fzf_reload.sh"
filter_cmd="$HOME/.config/tmux/scripts/pickers/session/filter.sh"
if [ -x "$fzf_reload_cmd" ] && [ -x "$filter_cmd" ] \
  && { [ -n "${FZF_SOCK:-}" ] || [ -n "${FZF_PORT:-}" ]; }; then
  "$fzf_reload_cmd" "$filter_cmd --refresh --force-order" 0 > /dev/null 2>&1 || true
fi

exit 0
