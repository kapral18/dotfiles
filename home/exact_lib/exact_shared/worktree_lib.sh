#!/usr/bin/env bash

# Sanitize a branch name for use as a filesystem path component.
# Replaces characters that break URL-based path resolution (e.g. Node.js
# import.meta.url parsed via new URL().pathname) where # is a fragment
# delimiter and ? starts a query string.  Git branch names allow these
# characters but filesystem paths containing them silently corrupt
# URL-derived __dirname calculations.
_comma_w_sanitize_path_component() {
  printf '%s\n' "$1" | sed 's/[#?%]/_/g'
}

_comma_w_herdr() {
  command -v herdr > /dev/null 2>&1 || return 127
  herdr "$@"
}

# True inside a herdr pane, popup, or custom command (herdr exports the API socket).
_comma_w_in_herdr() {
  [ -n "${HERDR_SOCKET_PATH:-}" ] && command -v herdr > /dev/null 2>&1
}

# "<workspace_id>\t<label>\t<dir>" rows: the directory each workspace was
# opened for (a pane cwd follows `cd`, so it cannot say that). One file per
# herdr server, since ids are per server. A row counts only while that id
# still carries that label, and the pickers plugin drops it when the
# workspace closes: herdr can reissue a closed workspace's id after a restart.
_comma_w_workspace_registry() {
  local sock="${HERDR_SOCKET_PATH:-${XDG_CONFIG_HOME:-$HOME/.config}/herdr/herdr.sock}"
  printf '%s/herdr-pickers/workspace_paths.%s.tsv\n' "${XDG_CACHE_HOME:-$HOME/.cache}" "$(printf '%s' "$sock" | cksum | cut -d' ' -f1)"
}

# Rows of the registry, less workspace $1 and every row whose workspace is
# gone (all rows are kept when herdr cannot list workspaces).
_comma_w_live_registry_rows() {
  local reg live listed=1
  reg="$(_comma_w_workspace_registry)"
  live="$(_comma_w_herdr workspace list 2> /dev/null | jq -er '.result.workspaces | map(.workspace_id) | join("\n")' 2> /dev/null)" || listed=0
  COMMA_W_LIVE_IDS="$live" awk -F'\t' -v id="${1:-}" -v listed="$listed" '
    BEGIN { n = split(ENVIRON["COMMA_W_LIVE_IDS"], ids, "\n"); for (i = 1; i <= n; i++) keep[ids[i]] = 1 }
    $1 != id && (!listed || ($1 in keep))
  ' "$reg" 2> /dev/null || true
}

_COMMA_W_LIB="${BASH_SOURCE[0]}"

# Run registry writer "$@" in a child bash holding an exclusive flock on the
# registry lock file: herdr runs plugin hooks concurrently with ,w, and each
# writer replaces the whole file. The kernel releases the lock when the
# holder exits or dies, so a stale lock cannot exist.
_comma_w_registry_locked() {
  local lock
  lock="$(_comma_w_workspace_registry).lock"
  mkdir -p "$(dirname "$lock")" 2> /dev/null || return 1
  perl -MFcntl=:flock -e '$^F = 255; open(my $fh, ">>", shift) or exit 1; flock($fh, LOCK_EX) or exit 1; exec @ARGV or exit 1' \
    "$lock" bash -c '. "$0"; "$@"' "$_COMMA_W_LIB" "$@"
}

# Rewrite the registry without workspace $1 (empty: only drop closed ones).
__comma_w_prune_workspace_registry() {
  local reg tmp
  reg="$(_comma_w_workspace_registry)"
  [ -f "$reg" ] || return 0
  tmp="$reg.$$"
  _comma_w_live_registry_rows "${1:-}" > "$tmp" && mv -f "$tmp" "$reg"
}

_comma_w_prune_workspace_registry() {
  _comma_w_registry_locked __comma_w_prune_workspace_registry "$@" || true
}

# After workspace $1 is renamed, keep its row under the new label so the
# opened-for directory survives the rename.
__comma_w_relabel_workspace() {
  local id="$1" reg label dir
  reg="$(_comma_w_workspace_registry)"
  [ -n "$id" ] && [ -f "$reg" ] || return 0
  dir="$(awk -F'\t' -v id="$id" '$1 == id { print $3; exit }' "$reg")"
  [ -n "$dir" ] || return 0
  label="$(_comma_w_herdr workspace list 2> /dev/null | jq -r --arg id "$id" '.result.workspaces[] | select(.workspace_id == $id) | .label' 2> /dev/null || true)"
  [ -n "$label" ] || return 0
  __comma_w_record_workspace_path "$id" "$label" "$dir"
}

_comma_w_relabel_workspace() {
  _comma_w_registry_locked __comma_w_relabel_workspace "$@" || true
}

__comma_w_record_workspace_path() {
  local id="$1" label="$2" dir="$3" reg tmp
  [ -n "$id" ] && [ -n "$label" ] && [ -n "$dir" ] || return 0
  reg="$(_comma_w_workspace_registry)"
  mkdir -p "$(dirname "$reg")"
  tmp="$reg.$$"
  {
    _comma_w_live_registry_rows "$id"
    printf '%s\t%s\t%s\n' "$id" "$label" "$dir"
  } > "$tmp"
  mv -f "$tmp" "$reg"
}

_comma_w_record_workspace_path() {
  _comma_w_registry_locked __comma_w_record_workspace_path "$@" || true
}

# "<label>\t<path>\t<workspace_id>\t<focused>" per workspace; path is the
# registered directory, else the first pane's cwd. With $1 = registered, only
# workspaces with a registered directory.
_comma_w_workspace_list() {
  local reg
  reg="$(_comma_w_workspace_registry)"
  jq -rn --arg mode "${1:-}" --rawfile reg <(cat "$reg" 2> /dev/null || true) \
    --argjson ws "$(_comma_w_herdr workspace list 2> /dev/null || echo '{}')" \
    --argjson panes "$(_comma_w_herdr pane list 2> /dev/null || echo '{}')" '
    ($reg | split("\n") | map(select(length > 0) | split("\t") | {(.[0]): {label: .[1], dir: .[2]}}) | add // {}) as $rows
    | ($panes.result.panes // []) as $p
    | ($ws.result.workspaces // [])[]
    | .workspace_id as $id
    | (if $rows[$id].label == .label then $rows[$id].dir else null end) as $dir
    | select($mode != "registered" or $dir != null)
    | [.label, ($dir // (first($p[] | select(.workspace_id == $id) | .cwd // empty) // "")), $id, (.focused | tostring)]
    | join("\t")' 2> /dev/null || true
}

# Workspace id whose label is exactly $1.
_comma_w_workspace_id_by_label() {
  _comma_w_herdr workspace list 2> /dev/null \
    | jq -r --arg label "$1" 'first(.result.workspaces[] | select(.label == $label) | .workspace_id) // empty' \
    || true
}

# Create workspace $1 at directory $2 without focusing it; print its id.
# With $3 = split, add a second pane to the right (the picker's default layout).
_comma_w_create_workspace() {
  local label="$1" dir="$2" layout="${3:-}" created
  created="$(_comma_w_herdr workspace create --cwd "$dir" --label "$label" --no-focus 2> /dev/null)" || return 1
  _comma_w_record_workspace_path "$(jq -r '.result.workspace.workspace_id' <<< "$created")" "$label" "$dir"
  if [ "$layout" = "split" ]; then
    _comma_w_herdr pane split "$(jq -r '.result.root_pane.pane_id' <<< "$created")" --direction right --cwd "$dir" --no-focus > /dev/null 2>&1 || true
  fi
  jq -r '.result.workspace.workspace_id' <<< "$created"
}

# True when workspace $1 has a pane whose cwd is directory $2 or below it.
_comma_w_workspace_has_pane_under() {
  local real pane_cwd
  real="$(_comma_w_resolved_path "$2")"
  while IFS= read -r pane_cwd; do
    case "$(_comma_w_resolved_path "$pane_cwd")" in
      "$real" | "$real"/*) return 0 ;;
    esac
  done < <(_comma_w_herdr pane list --workspace "$1" 2> /dev/null | jq -r '.result.panes[].cwd // empty' 2> /dev/null || true)
  return 1
}

# Ids of workspaces registered at exactly directory $1.
_comma_w_workspace_ids_at_path() {
  local target
  target="$(_comma_w_resolved_path "$1")"
  [ -n "$target" ] || return 0
  _comma_w_workspace_list registered | while IFS=$'\t' read -r _ ws_path ws_id _; do
    [ "$(_comma_w_resolved_path "$ws_path")" = "$target" ] && printf '%s\n' "$ws_id"
  done | sort -u || true
}

# "<workspace_id>\t<label>" for workspaces whose panes all report a cwd that no
# longer exists. Labels must start with "$1|" unless $1 is empty.
_comma_w_stale_workspaces() {
  local prefix="$1"
  local labels panes ws_id label pane_cwd
  labels="$(_comma_w_herdr workspace list 2> /dev/null | jq -r '.result.workspaces[] | [.workspace_id, .label] | join("\t")' 2> /dev/null || true)"
  panes="$(_comma_w_herdr pane list 2> /dev/null | jq -r '.result.panes[] | [.workspace_id, (.cwd // "")] | join("\t")' 2> /dev/null || true)"
  while IFS=$'\t' read -r ws_id label; do
    [ -n "$ws_id" ] || continue
    if [ -n "$prefix" ]; then
      case "$label" in "${prefix}|"*) ;; *) continue ;; esac
    fi
    local saw_any=0 alive=0
    while IFS=$'\t' read -r pane_ws pane_cwd; do
      [ "$pane_ws" = "$ws_id" ] && [ -n "$pane_cwd" ] || continue
      saw_any=1
      if [ -e "$pane_cwd" ]; then
        alive=1
        break
      fi
    done <<< "$panes"
    if [ "$saw_any" -eq 1 ] && [ "$alive" -eq 0 ]; then
      printf '%s\t%s\n' "$ws_id" "$label"
    fi
  done <<< "$labels"
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

_comma_w_workspace_name() {
  local parent_name="$1"
  local branch_name="$2"
  printf '%s|%s\n' "$parent_name" "$branch_name" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9_@|/~-]+/_/g; s/[.:]+/_/g; s/_+$//'
}

_comma_w_parent_name_from_dir() {
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

# Create the herdr workspace for a worktree unless one with its name exists.
_add_worktree_workspace() {
  local quiet_mode="${1:-0}"
  local parent_name="$2"
  local branch_name="$3"
  local worktree_path="$4"
  local workspace_name

  _comma_w_in_herdr || return 0

  workspace_name="$(_comma_w_workspace_name "$parent_name" "$branch_name")"
  [ -z "$(_comma_w_workspace_id_by_label "$workspace_name")" ] || return 0

  if [ "$quiet_mode" -eq 0 ]; then
    echo "

-------------

Adding herdr workspace: $workspace_name
At Path: $worktree_path
"
  fi

  if ! _comma_w_create_workspace "$workspace_name" "$worktree_path" > /dev/null; then
    if [ "$quiet_mode" -eq 0 ]; then
      echo "Warning: Failed to create herdr workspace '$workspace_name'." >&2
    fi
    return 1
  fi
}

# The path with symlinks resolved, even after the directory itself was removed.
_comma_w_resolved_path() {
  local parent
  [ -n "$1" ] || return 0
  realpath "$1" 2> /dev/null && return 0
  parent="$(realpath "$(dirname "$1")" 2> /dev/null)" || {
    printf '%s\n' "$1"
    return 0
  }
  printf '%s/%s\n' "${parent%/}" "$(basename "$1")"
}

# Close the workspace named $3 (when one of its panes sits under the worktree
# path) and every workspace registered at the worktree path, except the workspace id $4 (one
# the caller just created at the same path).
# COMMA_W_KEEP_WORKSPACES=1: the caller (the session picker) closes them itself.
_remove_worktree_workspace() {
  local quiet_mode="${1:-0}"
  local worktree_path="$2"
  local name_hint="${3:-}"
  local keep_id="${4:-}"
  local ids ws_id

  [ "${COMMA_W_KEEP_WORKSPACES:-0}" != 1 ] || return 0
  _comma_w_in_herdr || return 0
  [ -n "$worktree_path" ] || return 0

  local real_worktree hint_id
  real_worktree="$(_comma_w_resolved_path "$worktree_path")"
  ids="$(
    {
      if [ -n "$name_hint" ]; then
        hint_id="$(_comma_w_workspace_id_by_label "$name_hint")"
        if [ -n "$hint_id" ] && _comma_w_workspace_has_pane_under "$hint_id" "$real_worktree"; then
          printf '%s\n' "$hint_id"
        fi
      fi
      _comma_w_workspace_ids_at_path "$worktree_path"
    } | sort -u
  )"
  [ -n "$ids" ] || return 0

  if [ "$quiet_mode" -eq 0 ]; then
    echo "

-------------

Closing herdr workspaces: $(printf '%s ' $ids)
"
  fi
  for ws_id in $ids; do
    [ "$ws_id" != "$keep_id" ] || continue
    _comma_w_herdr workspace close "$ws_id" > /dev/null 2>&1 || true
  done
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

# Focus the workspace named $2, creating it at $3 when missing. Outside herdr,
# attach; the caller continues after the client detaches.
_comma_w_focus_workspace() {
  local quiet_mode="${1:-0}"
  local workspace_name="$2"
  local worktree_path="$3"
  local ws_id

  if ! command -v herdr > /dev/null 2>&1; then
    if [ "$quiet_mode" -eq 0 ]; then
      echo "Warning: 'herdr' is not available; cannot focus workspace '$workspace_name'." >&2
    fi
    return 1
  fi

  if ! _comma_w_herdr workspace list > /dev/null 2>&1; then
    # No server: bare `herdr` starts one through herdr's own launcher (a launchd
    # job on macOS, so it outlives this terminal). Once it answers, reuse a
    # restored workspace with this label, else take over the workspace herdr
    # seeds at this directory when no saved session exists, else create one;
    # then focus it. The poll outlasts herdr's own 15s wait for the server.
    local seeded=0
    jq -e '(.workspaces // []) | length > 0' "${XDG_CONFIG_HOME:-$HOME/.config}/herdr/session.json" > /dev/null 2>&1 || seeded=1
    (
      for _ in $(seq 200); do
        _comma_w_herdr workspace list > /dev/null 2>&1 || {
          sleep 0.1
          continue
        }
        ws_id="$(_comma_w_workspace_id_by_label "$workspace_name")"
        if [ -z "$ws_id" ]; then
          local listing
          listing="$(_comma_w_workspace_list)"
          if [ "$seeded" -eq 1 ] && [ "$(wc -l <<< "$listing")" -eq 1 ] \
            && [ "$(_comma_w_resolved_path "$(cut -f2 <<< "$listing")")" = "$(_comma_w_resolved_path "$worktree_path")" ]; then
            ws_id="$(cut -f3 <<< "$listing")"
            _comma_w_herdr workspace rename "$ws_id" "$workspace_name" > /dev/null 2>&1 \
              && _comma_w_record_workspace_path "$ws_id" "$workspace_name" "$worktree_path"
          else
            ws_id="$(_comma_w_create_workspace "$workspace_name" "$worktree_path" || true)"
          fi
        fi
        [ -z "$ws_id" ] || _comma_w_herdr workspace focus "$ws_id" > /dev/null 2>&1 || true
        exit 0
      done
    ) &
    (cd "$worktree_path" && herdr)
    return
  fi

  ws_id="$(_comma_w_workspace_id_by_label "$workspace_name")"
  if [ -z "$ws_id" ]; then
    ws_id="$(_comma_w_create_workspace "$workspace_name" "$worktree_path" || true)"
  fi
  if [ -z "$ws_id" ] || ! _comma_w_herdr workspace focus "$ws_id" > /dev/null 2>&1; then
    if [ "$quiet_mode" -eq 0 ]; then
      echo "Warning: failed to focus herdr workspace '$workspace_name'." >&2
    fi
    return 1
  fi

  _comma_w_in_herdr || herdr
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
      path="${url#git@*:}"
      ;;
    ssh://git@*/*/*)
      path="${url#ssh://git@*/}"
      ;;
    https://*/*/*)
      path="${url#https://*/}"
      ;;
    http://*/*/*)
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
