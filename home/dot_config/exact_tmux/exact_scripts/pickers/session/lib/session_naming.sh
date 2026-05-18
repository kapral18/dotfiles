#!/usr/bin/env bash
# session_naming.sh -- sourceable helpers shared between pick_session.sh and
# action_send_command.sh for computing canonical tmux session names from picker
# rows.
#
# The picker (`enter` handler in pick_session.sh) and the send-command action
# (`ctrl-s` consumer in action_send_command.sh) both need to convert a row
# `(kind, path, meta, target)` plus the configured `@pick_session_mode` into a
# tmux session name. Keeping the logic here is the only sane way to guarantee
# both code paths produce identical names; otherwise a `ctrl-s` spawn would
# create a session that the next `enter` on the same row treats as foreign and
# either renames or shadows.
#
# Functions (all defined unconditionally; safe to re-source):
#   resolve_path PATH                              -> realpath fallback
#   normalize                                      -> stdin -> stdout (kebab)
#   tildefy_to_reply PATH                          -> sets REPLY
#   tmux_sanitize_session_name NAME                -> stdout
#   session_name --directory|--full-path|--short-path INPUT...
#   login_shell                                    -> stdout (cached)
#   worktree_root_dir_for_path PATH                -> stdout
#   has_linked_worktrees_for_root_checkout ROOT    -> rc 0 if any linked wt
#   default_branch_for_root_checkout ROOT          -> stdout (branch name)
#   session_name_for_entry KIND PATH META TARGET MODE -> stdout
#
# Callers must run under bash 4+ (re-exec themselves on macOS bash 3.2). This
# file uses `${var,,}` lowercase expansion which requires bash 4.
#
# This file is intentionally idempotent: sourcing it twice is harmless.

# Guard against duplicate sourcing causing readonly redefinitions.
if [ "${__PICK_SESSION_NAMING_LOADED:-0}" = "1" ]; then
  # shellcheck disable=SC2317
  return 0 2> /dev/null || true
fi
__PICK_SESSION_NAMING_LOADED=1

resolve_path() {
  realpath "$1" 2> /dev/null || printf '%s' "$1"
}

normalize() {
  cat \
    | tr ' .:/' '-' \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/-+/-/g; s/^-+//; s/-+$//'
}

tildefy_to_reply() {
  local p="$1"
  # shellcheck disable=SC2034,SC2088
  case "$p" in
    "$HOME") REPLY="~" ;;
    "$HOME"/*) REPLY="~/${p#"$HOME"/}" ;;
    *) REPLY="$p" ;;
  esac
}

tmux_sanitize_session_name() {
  # tmux normalizes some characters in session names (notably '.'). Do minimal
  # sanitization so the name we target is the name tmux will actually create,
  # while preserving common branch separators like '/'.
  local s="${1-}"
  [ -n "$s" ] || return 1
  printf '%s\n' "$s" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9_@|/~-]+/_/g; s/[.:]+/_/g; s/_+$//'
}

session_name() {
  local input base out left right
  if [ "$1" = "--directory" ]; then
    shift
    input="${1-}"
    base="$(basename "$input")"
    case "$input" in
      "~") base="home" ;;
      *) if [ "$base" = "~" ]; then base="tilde"; fi ;;
    esac
    out="$(printf '%s\n' "$base" | normalize)"
    case "$out" in
      "" | "~") out="home" ;;
    esac
    printf '%s\n' "$out"
  elif [ "$1" = "--full-path" ]; then
    shift
    out="$(echo "$@" | normalize | sed 's/\\/$//')"
    case "$out" in
      "" | "~") out="home" ;;
    esac
    echo "$out"
  elif [ "$1" = "--short-path" ]; then
    shift
    left="$(echo "${@%/*}" | sed -E 's;/([^/]{1,2})[^/]*;/\1;g' | normalize)"
    right="$(basename "$@" | normalize)"
    case "$right" in
      "" | "~") right="home" ;;
    esac
    echo "${left}/${right}"
  else
    return 1
  fi
}

_pick_session_naming_cached_login_shell=""
login_shell() {
  if [ -n "$_pick_session_naming_cached_login_shell" ]; then
    printf '%s\n' "$_pick_session_naming_cached_login_shell"
    return 0
  fi
  _pick_session_naming_cached_login_shell="$(dscl . -read /Users/"$USER" UserShell 2> /dev/null | awk '{print $2}')"
  if [ -z "$_pick_session_naming_cached_login_shell" ] || [ ! -x "$_pick_session_naming_cached_login_shell" ]; then
    _pick_session_naming_cached_login_shell="$(getent passwd "$USER" 2> /dev/null | cut -d: -f7)"
  fi
  if [ -z "$_pick_session_naming_cached_login_shell" ] || [ ! -x "$_pick_session_naming_cached_login_shell" ]; then
    _pick_session_naming_cached_login_shell="$(command -v fish 2> /dev/null || echo /bin/sh)"
  fi
  printf '%s\n' "$_pick_session_naming_cached_login_shell"
}

worktree_root_dir_for_path() {
  local p="$1"
  [ -n "$p" ] || return 1
  p="$(resolve_path "$p")"
  if [ -f "$p" ]; then
    p="$(dirname "$p")"
  fi
  [ -d "$p" ] || return 1

  local common common_path
  common="$(git -C "$p" rev-parse --git-common-dir 2> /dev/null || true)"
  [ -n "$common" ] || return 1
  case "$common" in
    /*) common_path="$common" ;;
    *) common_path="$p/$common" ;;
  esac
  common_path="$(resolve_path "$common_path")"
  if [ "$(basename "$common_path")" = ".git" ]; then
    dirname "$common_path"
  else
    printf '%s\n' "$common_path"
  fi
}

has_linked_worktrees_for_root_checkout() {
  local root_checkout="$1"
  [ -n "$root_checkout" ] || return 1
  root_checkout="$(resolve_path "$root_checkout")"
  local wt_dir="$root_checkout/.git/worktrees"
  [ -d "$wt_dir" ] || return 1
  find "$wt_dir" -mindepth 1 -maxdepth 1 -print -quit 2> /dev/null | grep -q .
}

default_branch_for_root_checkout() {
  local root_checkout="$1"
  [ -n "$root_checkout" ] || return 1
  root_checkout="$(resolve_path "$root_checkout")"
  [ -d "$root_checkout" ] || return 1

  local out remote branch cand
  for remote in origin upstream; do
    out="$(git -C "$root_checkout" symbolic-ref --quiet --short "refs/remotes/$remote/HEAD" 2> /dev/null || true)"
    [ -n "$out" ] || continue
    case "$out" in
      "$remote"/*) branch="${out#"$remote"/}" ;;
      */*) branch="${out#*/}" ;;
      *) branch="$out" ;;
    esac
    case "${branch,,}" in
      ".invalid" | "invalid" | "(invalid)" | "") ;;
      *)
        printf '%s\n' "$branch"
        return 0
        ;;
    esac
  done

  for cand in main master trunk develop dev; do
    if git -C "$root_checkout" show-ref --verify --quiet "refs/heads/$cand" 2> /dev/null \
      || git -C "$root_checkout" show-ref --verify --quiet "refs/remotes/origin/$cand" 2> /dev/null \
      || git -C "$root_checkout" show-ref --verify --quiet "refs/remotes/upstream/$cand" 2> /dev/null; then
      printf '%s\n' "$cand"
      return 0
    fi
  done
  printf 'main\n'
  return 0
}

# session_name_for_entry KIND PATH META TARGET MODE
# Returns the canonical tmux session name for a picker row.
# `KIND` is one of: worktree, dir.
# `MODE` is the configured @pick_session_mode (directory | full-path | short-path).
# `TARGET` is the row's 5th cache field; for worktrees it's the wt_root path, for
# dirs it's unused. Pass empty string if unknown.
# Returns rc 1 for unsupported kinds (e.g. session, which already has a name).
session_name_for_entry() {
  local kind="$1" path="$2" meta="$3" target="${4-}" mode="${5:-directory}"
  case "$kind" in
    worktree)
      _session_name_for_worktree "$path" "$meta" "$target"
      ;;
    dir)
      _session_name_for_dir "$path" "$mode"
      ;;
    *)
      return 1
      ;;
  esac
}

_session_name_for_worktree() {
  local path="$1" meta="$2" target="$3"
  local branch="" repo_id="" name="" wt_root=""

  case "$meta" in
    wt_root:* | wt:*)
      branch="${meta#wt_root:}"
      branch="${branch#wt:}"
      branch="${branch%%|*}"
      ;;
  esac
  if [[ "$meta" == *"|repo="* ]]; then
    repo_id="${meta#*|repo=}"
    repo_id="${repo_id%%|*}"
  fi
  if [ -z "$repo_id" ]; then
    case "$path" in
      "$HOME"/*) repo_id="${path#"$HOME"/}" ;;
      *) repo_id="$path" ;;
    esac
  fi
  repo_id="$(tmux_sanitize_session_name "$repo_id" 2> /dev/null || printf '%s' "$repo_id")"

  # Branch fallback: only when meta lacked a branch AND the worktree root has
  # no linked checkouts. Matches pick_session.sh's enter-handler so ctrl-s
  # produces the same name as a regular enter would.
  wt_root="$target"
  [ -n "$wt_root" ] || wt_root="$(worktree_root_dir_for_path "$path" 2> /dev/null || true)"
  [ -n "$wt_root" ] || wt_root="$path"
  if [ -z "$branch" ] && ! has_linked_worktrees_for_root_checkout "$wt_root"; then
    branch="$(default_branch_for_root_checkout "$wt_root" 2> /dev/null || true)"
  fi
  case "${branch,,}" in
    ".invalid" | "invalid" | "(invalid)") branch="" ;;
  esac
  branch="$(tmux_sanitize_session_name "$branch" 2> /dev/null || printf '%s' "$branch")"

  if [ -n "$branch" ] && [ -n "$repo_id" ]; then
    name="${repo_id}|${branch}"
  elif [ -n "$repo_id" ]; then
    name="$repo_id"
  elif [ -n "$branch" ]; then
    name="$branch"
  else
    name="$(basename "$path")"
  fi
  tmux_sanitize_session_name "$name" 2> /dev/null || printf '%s' "$name"
}

_session_name_for_dir() {
  local path="$1" mode="${2:-directory}"
  local dir_with_tilde="$path" name=""
  # shellcheck disable=SC2088
  case "$path" in
    "$HOME") dir_with_tilde="~" ;;
    "$HOME"/*) dir_with_tilde="~/${path#"$HOME"/}" ;;
  esac
  name="$(session_name "--${mode}" "$dir_with_tilde" 2> /dev/null || true)"
  if [ -z "$name" ]; then
    return 1
  fi
  tmux_sanitize_session_name "$name" 2> /dev/null || printf '%s' "$name"
}

# bag_rename_if_needed DESIRED_NAME TARGET_PATH [EXISTING_PATH]
# Sole implementation of pick_session.sh's @bag-recovery flow. When tmux already
# has a session named DESIRED_NAME pointing at a path under
# ~/.bag/worktree_remove/ or ~/.bag/pickers/session/, rename that session to
# `${DESIRED_NAME}@bag[<n>]` so the caller can create its own session at the
# real TARGET_PATH. Returns 0 if the name is now free for use (either because
# it never was held, the holder was bagged-and-renamed, or it already points
# at TARGET_PATH); returns 1 if the name is held by a non-bagged session at a
# different path (caller must pick a different name).
#
# When EXISTING_PATH is provided, skips the internal `tmux list-sessions`
# lookup — callers maintaining their own session cache (pick_session.sh's
# `sess_path_for_name`) pass it in to avoid an extra fork on the hot `enter`
# path. When omitted, the lookup uses `tmux list-sessions` (works without an
# attached client; `display-message -p` requires one and silently returns
# empty otherwise).
#
# On a successful rename, prints "OLD_NAME\tNEW_NAME" to stdout so caller-side
# caches can be updated; prints nothing when no rename occurred. The return
# code is the source of truth for "name is usable"; stdout is purely an
# advisory channel for cache maintenance.
bag_rename_if_needed() {
  local desired_name="$1" target_path="$2" existing_path="${3-}"
  [ -n "$desired_name" ] || return 1
  if ! tmux has-session -t "=${desired_name}" 2> /dev/null; then
    return 0
  fi
  if [ -z "$existing_path" ]; then
    local _ln _lp
    while IFS=$'\t' read -r _ln _lp; do
      if [ "$_ln" = "$desired_name" ]; then
        existing_path="$_lp"
        break
      fi
    done < <(tmux list-sessions -F $'#{session_name}\t#{session_path}' 2> /dev/null || true)
  fi
  local existing_rp desired_rp
  existing_rp="$(resolve_path "$existing_path" 2> /dev/null || printf '%s' "$existing_path")"
  desired_rp="$(resolve_path "$target_path" 2> /dev/null || printf '%s' "$target_path")"
  if [ -n "$existing_rp" ] && [ -n "$desired_rp" ] && [ "$existing_rp" = "$desired_rp" ]; then
    return 0
  fi
  case "$existing_rp" in
    "$HOME"/.bag/worktree_remove/* | "$HOME"/.bag/pickers/session/* | */.bag/worktree_remove/* | */.bag/pickers/session/*) ;;
    *) return 1 ;;
  esac
  local bag_name n cand
  bag_name="${desired_name}@bag"
  bag_name="$(tmux_sanitize_session_name "$bag_name" 2> /dev/null || printf '%s' "$bag_name")"
  if [ -z "$bag_name" ] || [ "$bag_name" = "$desired_name" ]; then
    return 1
  fi
  if tmux has-session -t "=${bag_name}" 2> /dev/null; then
    n=2
    while [ "$n" -le 50 ]; do
      cand="${bag_name}${n}"
      if ! tmux has-session -t "=${cand}" 2> /dev/null; then
        bag_name="$cand"
        break
      fi
      n="$((n + 1))"
    done
    if [ "$n" -gt 50 ]; then
      return 1
    fi
  fi
  tmux rename-session -t "=${desired_name}" "$bag_name" 2> /dev/null || return 1
  printf '%s\t%s\n' "$desired_name" "$bag_name"
  return 0
}
