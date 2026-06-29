#!/usr/bin/env bash
# Worktree helper functions library

# Sanitize a branch name for use as a filesystem path component.
# Replaces characters that break URL-based path resolution (e.g. Node.js
# import.meta.url parsed via new URL().pathname) where # is a fragment
# delimiter and ? starts a query string.  Git branch names allow these
# characters but filesystem paths containing them silently corrupt
# URL-derived __dirname calculations.
_comma_w_sanitize_path_component() {
  printf '%s\n' "$1" | sed 's/[#?%]/_/g'
}

_comma_w_tmux() {
  if ! command -v tmux > /dev/null 2>&1; then
    return 127
  fi

  # When running inside the persistent gh-dash popup, we want tmux operations
  # (session creation/focus/etc.) to affect the *outer* tmux server, not the
  # nested one. The popup launcher exports these.
  if [ -n "${OUTER_TMUX_SOCKET:-}" ]; then
    tmux -S "${OUTER_TMUX_SOCKET}" "$@"
    return $?
  fi

  tmux "$@"
}

_comma_w_login_shell() {
  local s=""
  s="$(python3 -c 'import os,pwd; print(pwd.getpwuid(os.getuid()).pw_shell)' 2> /dev/null || true)"
  if [ -n "$s" ] && [ -x "$s" ]; then
    printf '%s\n' "$s"
    return 0
  fi
  command -v fish 2> /dev/null || printf '%s\n' /bin/sh
}

_comma_w_prune_stale_worktrees() {
  local quiet_mode="${1:-0}"
  if [ "${__COMMA_W_PRUNE_RAN:-0}" -eq 1 ]; then
    return
  fi
  __COMMA_W_PRUNE_RAN=1

  case "${COMMA_W_PRUNE:-1}" in
    0 | false | no | off)
      return
      ;;
  esac

  local dry_run_output
  dry_run_output="$(git worktree prune --dry-run 2>&1 || true)"
  if [ -z "${dry_run_output//[[:space:]]/}" ]; then
    return
  fi

  if [ "$quiet_mode" -eq 0 ]; then
    echo "Pruning stale git worktree metadata..."
  fi

  git worktree prune 2>&1 || true
}

# Print created worktree message
_print_created_worktree_message() {
  local quiet_mode="${1:-0}"
  local branch_name="$2"
  local worktree_path="$3"
  local from_branch="${4:-}"

  if [ "$quiet_mode" -eq 1 ]; then
    return
  fi

  echo "

-------------

Created new worktree
For Branch: $branch_name
At Path: $worktree_path"

  if [ -n "$from_branch" ]; then
    echo "From Branch: $from_branch"
  else
    echo "From Current Branch"
  fi
}

_comma_w_tmux_session_name() {
  local parent_name="$1"
  local branch_name="$2"
  # tmux normalizes some session name characters (for example '.' -> '_').
  # Normalize up-front so create/switch/remove paths all target the same name.
  printf '%s|%s\n' "$parent_name" "$branch_name" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9_@|/~-]+/_/g; s/[.:]+/_/g; s/_+$//'
}

_comma_w_tmux_parent_name_from_dir() {
  local parent_dir="$1"
  local rp home_rp

  rp="$(realpath "$parent_dir" 2> /dev/null || printf '%s' "$parent_dir")"
  home_rp="$(realpath "${HOME:-}" 2> /dev/null || printf '%s' "${HOME:-}")"

  if [ -n "$home_rp" ]; then
    case "$rp" in
      "$home_rp")
        printf '%s\n' "home"
        return 0
        ;;
      "$home_rp"/*)
        printf '%s\n' "${rp#"$home_rp"/}"
        return 0
        ;;
    esac
  fi

  printf '%s\n' "$(basename "$rp")"
}

# Add worktree tmux session
_add_worktree_tmux_session() {
  local quiet_mode="${1:-0}"
  local parent_name="$2"
  local branch_name="$3"
  local worktree_path="$4"

  if [ -n "${TMUX:-}" ]; then
    if ! command -v tmux > /dev/null 2>&1; then
      if [ "$quiet_mode" -eq 0 ]; then
        echo "Warning: TMUX is set but 'tmux' is not available; skipping session creation." >&2
      fi
      return 0
    fi

    local session_name
    session_name="$(_comma_w_tmux_session_name "$parent_name" "$branch_name")"

    if _comma_w_tmux has-session -t "$session_name" 2> /dev/null; then
      return 0
    fi

    if [ "$quiet_mode" -eq 0 ]; then
      echo "

-------------

Adding TMUX Session: $parent_name|$branch_name
At Path: $worktree_path
"
    fi

    local shell="$(_comma_w_login_shell)"
    if ! _comma_w_tmux new-session -d -s "$session_name" -c "$worktree_path" "$shell" 2> /dev/null; then
      if [ "$quiet_mode" -eq 0 ]; then
        echo "Warning: Failed to create tmux session '$session_name'." >&2
      fi
    fi
  fi
}

# Remove worktree tmux session
_remove_worktree_tmux_session() {
  if [ -n "${TMUX:-}" ]; then
    local quiet_mode="${1:-0}"
    local worktree_path="$2"
    local session_name_hint="${3:-}"
    local -a session_names=()
    local session_names_seen=" "
    local session_name
    local session_path

    _add_session_name() {
      local name="$1"
      case "$session_names_seen" in
        *" ${name} "*)
          return 0
          ;;
      esac
      session_names+=("$name")
      session_names_seen+="${name} "
    }

    if [ -n "$session_name_hint" ] && _comma_w_tmux has-session -t "$session_name_hint" 2> /dev/null; then
      _add_session_name "$session_name_hint"
    fi

    while IFS=$'\t' read -r session_name session_path; do
      if [ "$session_path" = "$worktree_path" ]; then
        _add_session_name "$session_name"
      fi
    done < <(_comma_w_tmux list-sessions -F $'#{session_name}\t#{session_path}' 2> /dev/null || true)

    if [ "$quiet_mode" -eq 0 ]; then
      echo "

-------------

Removing TMUX Session: ${session_names[*]:-}
"
    fi
    # Guard against bash 3.2 (default `/bin/bash` on macOS) treating an empty
    # array expansion as an unbound variable under `set -u`. Direct callers
    # like `,w remove` source this lib without a bash 4+ re-exec, so we hit
    # this branch when no matching tmux sessions exist for the path.
    for session_name in "${session_names[@]+"${session_names[@]}"}"; do
      _comma_w_tmux kill-session -t "$session_name" 2> /dev/null || true
    done
  fi
}

_comma_w_find_worktree_path_for_branch() {
  local branch="$1"
  local line
  local worktree_path=""
  local target="branch refs/heads/${branch}"

  while IFS= read -r line; do
    case "$line" in
      worktree\ *)
        worktree_path="${line#worktree }"
        ;;
      "$target")
        if [ -n "$worktree_path" ]; then
          printf '%s\n' "$worktree_path"
          return 0
        fi
        ;;
    esac
  done < <(git worktree list --porcelain)

  return 1
}

_comma_w_focus_tmux_session() {
  local quiet_mode="${1:-0}"
  local session_name="$2"
  local worktree_path="$3"
  local fallback_client=""

  if ! command -v tmux > /dev/null 2>&1; then
    if [ "$quiet_mode" -eq 0 ]; then
      echo "Warning: 'tmux' is not available; cannot focus session '$session_name'." >&2
    fi
    return 1
  fi

  if [ -n "${OUTER_TMUX_SOCKET:-}" ]; then
    if [ -n "${OUTER_TMUX_CLIENT:-}" ] \
      && _comma_w_tmux switch-client -c "${OUTER_TMUX_CLIENT}" -t "$session_name" 2> /dev/null; then
      return 0
    fi

    fallback_client="$(_comma_w_tmux list-clients -F '#{client_name}' 2> /dev/null | sed -n '1p')"
    if [ -n "$fallback_client" ] \
      && _comma_w_tmux switch-client -c "$fallback_client" -t "$session_name" 2> /dev/null; then
      return 0
    fi

    if _comma_w_tmux switch-client -t "$session_name" 2> /dev/null; then
      return 0
    fi
  fi

  if [ -n "${TMUX:-}" ]; then
    if _comma_w_tmux switch-client -t "$session_name" 2> /dev/null; then
      return 0
    fi
    if [ "$quiet_mode" -eq 0 ]; then
      echo "Warning: failed to switch tmux client to session '$session_name'." >&2
    fi
    return 1
  fi

  if _comma_w_tmux attach-session -t "$session_name" 2> /dev/null; then
    return 0
  fi
  local shell="$(_comma_w_login_shell)"
  _comma_w_tmux new-session -s "$session_name" -c "$worktree_path" "$shell"
}

_comma_w_worktree_has_branch() {
  local branch="$1"
  local target="branch refs/heads/${branch}"
  local line

  while IFS= read -r line; do
    case "$line" in
      "$target") return 0 ;;
    esac
  done < <(git worktree list --porcelain 2> /dev/null)

  return 1
}

_comma_w_any_remote_has_branch() {
  local branch="$1"
  local remote

  while IFS= read -r remote; do
    [ -z "$remote" ] && continue
    if git show-ref --verify --quiet "refs/remotes/${remote}/${branch}" 2> /dev/null; then
      return 0
    fi
  done < <(git remote 2> /dev/null || true)

  return 1
}

_comma_w_branch_exists_locally_or_remote() {
  local branch="$1"
  if git show-ref --verify --quiet "refs/heads/${branch}" 2> /dev/null; then
    return 0
  fi
  _comma_w_any_remote_has_branch "$branch"
}

_comma_w_detect_default_branch() {
  local ref
  local remote
  for remote in upstream origin; do
    ref="$(git symbolic-ref -q --short "refs/remotes/${remote}/HEAD" 2> /dev/null || true)"
    if [ -n "$ref" ]; then
      printf '%s\n' "${ref#${remote}/}"
      return 0
    fi
  done

  local b
  for b in main master dev develop trunk; do
    if git show-ref --verify --quiet "refs/heads/${b}" 2> /dev/null \
      || git show-ref --verify --quiet "refs/remotes/origin/${b}" 2> /dev/null \
      || git show-ref --verify --quiet "refs/remotes/upstream/${b}" 2> /dev/null; then
      printf '%s\n' "$b"
      return 0
    fi
  done

  printf '%s\n' "main"
}

__COMMA_W_GH_LOGIN_CACHE="${__COMMA_W_GH_LOGIN_CACHE:-}"
__COMMA_W_GH_LOGIN_CACHE_SET="${__COMMA_W_GH_LOGIN_CACHE_SET:-0}"

_comma_w_get_github_login() {
  if [ "${__COMMA_W_GH_LOGIN_CACHE_SET}" -eq 1 ]; then
    printf '%s\n' "${__COMMA_W_GH_LOGIN_CACHE}"
    return 0
  fi

  __COMMA_W_GH_LOGIN_CACHE_SET=1
  __COMMA_W_GH_LOGIN_CACHE=""

  if command -v gh > /dev/null 2>&1; then
    __COMMA_W_GH_LOGIN_CACHE="$(gh api user --jq '.login' 2> /dev/null || true)"
  fi

  if [ -z "${__COMMA_W_GH_LOGIN_CACHE}" ]; then
    __COMMA_W_GH_LOGIN_CACHE="${GITHUB_USER:-${USER:-}}"
  fi

  printf '%s\n' "${__COMMA_W_GH_LOGIN_CACHE}"
}

_comma_w_parse_owner_repo_from_remote_url() {
  local url="$1"
  local path=""

  url="${url%.git}"
  case "$url" in
    git@*:*/*)
      # git@<host>:owner/repo
      path="${url#git@*:}"
      ;;
    ssh://git@*/*/*)
      # ssh://git@<host>/owner/repo
      path="${url#ssh://git@*/}"
      ;;
    https://*/*/*)
      # https://<host>/owner/repo
      path="${url#https://*/}"
      ;;
    http://*/*/*)
      # http://<host>/owner/repo
      path="${url#http://*/}"
      ;;
    *)
      return 1
      ;;
  esac

  if [[ "$path" != */* ]]; then
    return 1
  fi

  printf '%s\t%s\n' "${path%%/*}" "${path#*/}"
}

_comma_w_get_remote_owner() {
  local remote="$1"
  local remote_url parsed

  remote_url="$(git remote get-url "$remote" 2> /dev/null || true)"
  if [ -z "$remote_url" ]; then
    return 1
  fi

  parsed="$(_comma_w_parse_owner_repo_from_remote_url "$remote_url" 2> /dev/null || true)"
  if [ -z "$parsed" ]; then
    return 1
  fi

  printf '%s\n' "${parsed%%$'\t'*}"
}

_comma_w_remote_is_first_party() {
  local remote="$1"
  local github_login remote_owner

  case "$remote" in
    origin | upstream)
      return 0
      ;;
  esac

  github_login="$(_comma_w_get_github_login)"
  if [ -n "$github_login" ] && [ "$remote" = "$github_login" ]; then
    return 0
  fi

  remote_owner="$(_comma_w_get_remote_owner "$remote" 2> /dev/null || true)"
  if [ -n "$github_login" ] && [ -n "$remote_owner" ] && [ "$remote_owner" = "$github_login" ]; then
    return 0
  fi

  return 1
}

_comma_w_remote_has_branch_ref() {
  local remote="$1"
  local branch="$2"
  git show-ref --verify --quiet "refs/remotes/${remote}/${branch}" 2> /dev/null
}

_comma_w_preferred_tracking_remote_for_branch() {
  local preferred_remote="$1"
  local branch="$2"
  local remote

  if ! _comma_w_remote_is_first_party "$preferred_remote"; then
    printf '%s\n' "$preferred_remote"
    return 0
  fi

  for remote in origin upstream; do
    if git remote get-url "$remote" > /dev/null 2>&1 && _comma_w_remote_has_branch_ref "$remote" "$branch"; then
      printf '%s\n' "$remote"
      return 0
    fi
  done

  if _comma_w_remote_has_branch_ref "$preferred_remote" "$branch"; then
    printf '%s\n' "$preferred_remote"
    return 0
  fi

  while IFS= read -r remote; do
    [ -n "$remote" ] || continue
    case "$remote" in
      origin | upstream | "$preferred_remote") continue ;;
    esac
    if _comma_w_remote_is_first_party "$remote" && _comma_w_remote_has_branch_ref "$remote" "$branch"; then
      printf '%s\n' "$remote"
      return 0
    fi
  done < <(git remote 2> /dev/null || true)

  printf '%s\n' "$preferred_remote"
}

# Configure per-worktree push routing for prefixed local branches
# (<remote>__<branch>) so plain `git push` targets the fork branch.
_comma_w_configure_prefixed_branch_push_routing() {
  local worktree_path="$1"
  local local_branch="$2"
  local push_remote="$3"
  local remote_branch="$4"
  local quiet_mode="${5:-0}"

  if [ -z "$worktree_path" ] || [ -z "$local_branch" ] || [ -z "$push_remote" ] || [ -z "$remote_branch" ]; then
    return 1
  fi

  if [ ! -d "$worktree_path" ]; then
    return 1
  fi

  # Keep push routing isolated to this worktree.
  git config extensions.worktreeConfig true
  git -C "$worktree_path" config --worktree remote.pushDefault "$push_remote"
  git -C "$worktree_path" config --worktree push.default upstream

  # Always set tracking explicitly so behavior is stable even when
  # branch.autoSetupMerge is disabled in user/global git config.
  git -C "$worktree_path" config "branch.${local_branch}.remote" "$push_remote"
  git -C "$worktree_path" config "branch.${local_branch}.merge" "refs/heads/${remote_branch}"

  if [ "$quiet_mode" -eq 0 ]; then
    echo "Configured per-worktree smart push routing -> ${push_remote}/${remote_branch}"
  fi
}
