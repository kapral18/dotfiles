#!/usr/bin/env bash
# session_naming.sh -- sourceable helpers shared between pick_session.sh and
# action_send_command.sh for computing canonical workspace names from picker
# rows.
# Callers must run under bash 4+ (re-exec themselves on macOS bash 3.2). This
# file uses `${var,,}` lowercase expansion which requires bash 4.

# Guard against duplicate sourcing causing readonly redefinitions.
if [ "${__PICK_SESSION_NAMING_LOADED:-0}" = "1" ]; then
  # shellcheck disable=SC2317
  return 0 2> /dev/null || true
fi
__PICK_SESSION_NAMING_LOADED=1

picker_row_parse() {
  local row="${1-}"
  PICKER_ROW_FIELDS=()
  mapfile -t PICKER_ROW_FIELDS < <(
    printf '%s\n' "$row" | awk -F $'\t' '{ for (i = 1; i <= 6; i++) print $i }'
  )
}

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

# Same normalization as ,w (_comma_w_workspace_name), so both name a
# directory's workspace identically; keeps branch separators like '/'.
sanitize_session_name() {
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
# Returns the canonical workspace name for a picker row.
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
  repo_id="$(sanitize_session_name "$repo_id" 2> /dev/null || printf '%s' "$repo_id")"

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
  branch="$(sanitize_session_name "$branch" 2> /dev/null || printf '%s' "$branch")"

  if [ -n "$branch" ] && [ -n "$repo_id" ]; then
    name="${repo_id}|${branch}"
  elif [ -n "$repo_id" ]; then
    name="$repo_id"
  elif [ -n "$branch" ]; then
    name="$branch"
  else
    name="$(basename "$path")"
  fi
  sanitize_session_name "$name" 2> /dev/null || printf '%s' "$name"
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
  sanitize_session_name "$name" 2> /dev/null || printf '%s' "$name"
}
