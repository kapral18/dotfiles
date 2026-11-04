#!/usr/bin/env bash

_comma_w_issue_normalize_number() {
  local input="$1"
  local issue_number=""

  if [[ "$input" =~ ^#[0-9]+$ ]]; then
    issue_number="${input#\#}"
  elif [[ "$input" =~ ^[0-9]+$ ]]; then
    issue_number="$input"
  elif [[ "$input" =~ ^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/([0-9]+)([/?#].*)?$ ]]; then
    issue_number="${BASH_REMATCH[1]}"
  else
    return 1
  fi

  printf '%s\n' "$issue_number"
}

_comma_w_issue_url_repo() {
  local input="$1"
  if [[ "$input" =~ ^https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/issues/[0-9]+([/?#].*)?$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
  fi
}

_comma_w_issue_get_repo_name() {
  gh repo view --json nameWithOwner --jq '.nameWithOwner' 2> /dev/null || true
}

_comma_w_issue_can_associate() {
  local worktree_path="$1" repo_name="$2" issue_number="$3"
  local stored_repo stored_number
  stored_repo="$(git -C "$worktree_path" config --worktree --get comma.w.issue.repo 2> /dev/null || true)"
  stored_number="$(git -C "$worktree_path" config --worktree --get comma.w.issue.number 2> /dev/null || true)"
  if [ -n "$stored_repo" ] && [ "$(printf '%s' "$stored_repo" | tr '[:upper:]' '[:lower:]')" != "$(printf '%s' "$repo_name" | tr '[:upper:]' '[:lower:]')" ]; then
    return 1
  fi
  [ -z "$stored_number" ] || [ "$stored_number" = "$issue_number" ]
}

_comma_w_issue_find_by_metadata() {
  local repo_name="$1"
  local issue_number="$2"
  local line key value worktree_path=""

  while IFS= read -r line; do
    key="${line%% *}"
    value="${line#* }"
    case "$key" in
      worktree)
        worktree_path="$value"
        if [ -z "$worktree_path" ] || [ ! -e "$worktree_path/.git" ]; then
          continue
        fi

        local wt_repo wt_num
        wt_repo="$(git -C "$worktree_path" config --worktree --get comma.w.issue.repo 2> /dev/null || true)"
        wt_num="$(git -C "$worktree_path" config --worktree --get comma.w.issue.number 2> /dev/null || true)"
        if [ "$wt_repo" = "$repo_name" ] && [ "$wt_num" = "$issue_number" ]; then
          printf '%s\n' "$worktree_path"
          return 0
        fi
        ;;
    esac
  done < <(git worktree list --porcelain 2> /dev/null)

  return 1
}

_comma_w_issue_find_by_heuristics() {
  local issue_number="$1"
  local repo_name="$2"
  local -a candidates=()
  local candidates_seen=" "
  local line key value worktree_path="" branch_ref=""

  _branch_prefers_issue_number() {
    local branch="$1"
    printf '%s' "$branch" | grep -Eq "(-|/)${issue_number}$"
  }

  _maybe_add_candidate() {
    local p="$1"
    local br_ref="$2"
    [ -n "$p" ] || return 0
    [[ "$br_ref" == refs/heads/* ]] || return 0
    _branch_prefers_issue_number "${br_ref#refs/heads/}" || return 0
    _comma_w_issue_can_associate "$p" "$repo_name" "$issue_number" || return 0
    case "$candidates_seen" in
      *" ${p} "*) return 0 ;;
    esac
    candidates+=("$p")
    candidates_seen+="${p} "
  }

  while IFS= read -r line; do
    key="${line%% *}"
    value="${line#* }"
    case "$key" in
      worktree)
        _maybe_add_candidate "$worktree_path" "$branch_ref"
        worktree_path="$value"
        branch_ref=""
        ;;
      branch)
        branch_ref="$value"
        ;;
    esac
  done < <(git worktree list --porcelain 2> /dev/null)

  _maybe_add_candidate "$worktree_path" "$branch_ref"

  if [ "${#candidates[@]}" -gt 0 ]; then
    printf '%s\n' "${candidates[0]}"
    return 0
  fi

  return 1
}

_comma_w_issue_store_metadata() {
  local worktree_path="$1"
  local repo_name="$2"
  local issue_number="$3"

  _comma_w_issue_can_associate "$worktree_path" "$repo_name" "$issue_number" || return 1
  git config extensions.worktreeConfig true || return
  git -C "$worktree_path" config --worktree comma.w.issue.repo "$repo_name" || return
  git -C "$worktree_path" config --worktree comma.w.issue.number "$issue_number"
}
