#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "$0")/../bash_utils_lib.sh"
source "$(dirname "$0")/../worktree_lib.sh"
source "$(dirname "$0")/issue_lib.sh"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" > /dev/null 2>&1; then
    echo "Missing required dependency: '$cmd'." >&2
    exit 1
  fi
}

show_usage() {
  cat << 'EOF'
Usage: ,w issue [-q|--quiet] [--focus] [-b|--branch <name>] <issue_number|url>

Create or reuse a worktree for a GitHub issue.

This command:
- Reuses an existing issue worktree (metadata or issue-number heuristic) when available
- Prompts for a branch name when creating a new issue worktree
- Creates new branches as: <branch_name>-<issue_number>
- Stores issue metadata in per-worktree git config

Options:
  -q, --quiet       Suppress informational output
  --focus           Switch/attach to the worktree's tmux session
  -b, --branch      Use the provided branch name instead of prompting
  -h, --help        Show this help message
EOF
}

quiet_mode=0
focus_mode=0
manual_branch="${COMMA_W_ISSUE_BRANCH:-}"

while [ $# -gt 0 ]; do
  case "$1" in
    -h | --help)
      show_usage
      exit 0
      ;;
    -q | --quiet)
      quiet_mode=1
      shift
      ;;
    --focus)
      focus_mode=1
      shift
      ;;
    -b | --branch)
      if [ $# -lt 2 ]; then
        echo ",w issue: missing value for $1" >&2
        exit 1
      fi
      manual_branch="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    -*)
      show_usage >&2
      exit 1
      ;;
    *)
      break
      ;;
  esac
done

info() {
  if [ "$quiet_mode" -eq 0 ]; then
    printf '%s\n' "$@"
  fi
}

die() {
  echo ",w issue: $*" >&2
  exit 1
}

trim_whitespace() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s\n' "$s"
}

normalize_branch_input() {
  local branch="$1"
  branch="$(trim_whitespace "$branch")"
  # Users sometimes paste tmux session names (parent|branch) into this prompt.
  # Branch names must be git-valid and our tooling uses '|' as a session separator,
  # so treat anything before the last '|' as a prefix and strip it.
  case "$branch" in
    *'|'*) branch="${branch##*|}" ;;
  esac
  branch="${branch#refs/heads/}"
  while [[ "$branch" == /* ]]; do
    branch="${branch#/}"
  done
  printf '%s\n' "$branch"
}

validate_branch_name() {
  local branch="$1"
  [ -n "$branch" ] || return 1
  case "$branch" in
    *'|'*) return 1 ;;
  esac
  git check-ref-format --branch "$branch" > /dev/null 2>&1
}

with_issue_suffix() {
  local branch="$1"
  local issue_number="$2"
  branch="${branch%-${issue_number}}"
  printf '%s-%s\n' "$branch" "$issue_number"
}

prompt_branch_name() {
  local issue_number="$1"
  local issue_title="$2"
  local ch=""
  local buf=""
  local esc=""
  local ctrl_c=""
  local cr=""
  local nl=""
  local bs=""
  local prompt_prefix=""
  local hint=""

  # Inside tmux display-popup -E, stdin might not be a standard tty,
  # but /dev/tty is available. We read from /dev/tty directly below.

  esc="$(printf '\033')"
  ctrl_c="$(printf '\003')"
  cr="$(printf '\r')"
  nl="$(printf '\n')"
  bs="$(printf '\177')"
  prompt_prefix="\033[38;5;111m\033[0m \033[38;5;244mbranch\033[0m \033[38;5;244m(without issue suffix)\033[0m \033[38;5;244m>\033[0m "
  hint="\033[38;5;240m(e.g. feat/my-change, esc to cancel)\033[0m"

  printf '\n\033[38;5;111mIssue #%s:\033[0m %s\n\n' "$issue_number" "$issue_title" >&2
  printf "%b%b" "$prompt_prefix" "$hint" >&2
  printf "\r%b" "$prompt_prefix" >&2

  while IFS= read -rsn 1 ch < /dev/tty; do
    case "$ch" in
      "$ctrl_c")
        return 1
        ;;
      "$esc")
        # Distinguish bare ESC from arrow/function key escape sequences.
        # If another byte arrives within 10ms it's part of a sequence — consume and ignore it.
        if IFS= read -rsn 1 -t 0.01 seq_ch < /dev/tty 2> /dev/null; then
          # Consume the rest of the CSI sequence (e.g. [A, [B, [C, [D, [H, [F, …)
          while IFS= read -rsn 1 -t 0.01 _ < /dev/tty 2> /dev/null; do :; done
        else
          return 1
        fi
        ;;
      "$cr" | "$nl")
        break
        ;;
      "$bs" | $'\b')
        if [ -n "$buf" ]; then
          buf="${buf%?}"
        fi
        ;;
      *)
        buf+="$ch"
        ;;
    esac
    printf "\r%b%s\033[K" "$prompt_prefix" "$buf" >&2
  done

  printf '\n' >&2
  normalize_branch_input "$buf"
}

if [ $# -ne 1 ]; then
  show_usage >&2
  exit 1
fi

require_cmd gh
require_cmd git

issue_input="$1"
issue_number="$(_comma_w_issue_normalize_number "$issue_input" || true)"
if [ -z "$issue_number" ]; then
  die "invalid issue number or url: $issue_input"
fi

repo_name="$(_comma_w_issue_get_repo_name)"
if [ -z "$repo_name" ]; then
  die "failed to determine repo name (are you in a git repo and authenticated with gh?)"
fi

_comma_w_prune_stale_worktrees "$quiet_mode"

existing_path="$(_comma_w_issue_find_by_metadata "$repo_name" "$issue_number" 2> /dev/null || true)"
if [ -z "$existing_path" ]; then
  existing_path="$(_comma_w_issue_find_by_heuristics "$issue_number" 2> /dev/null || true)"
fi

if [ -n "$existing_path" ]; then
  info "Found existing issue worktree for #$issue_number at: $existing_path"
  _comma_w_issue_store_metadata "$existing_path" "$repo_name" "$issue_number" || true
  if [ "$focus_mode" -eq 1 ]; then
    "$(dirname "$0")/open.sh" -q "$existing_path"
  fi
  exit 0
fi

manual_branch="$(normalize_branch_input "$manual_branch")"

if [ -z "$manual_branch" ]; then
  issue_title="$(gh issue view "$issue_number" --json title --jq '.title' 2> /dev/null || true)"
  if [ -z "$issue_title" ]; then
    issue_title="(unable to fetch title)"
  fi

  manual_branch="$(prompt_branch_name "$issue_number" "$issue_title")" || exit 0
  manual_branch="$(normalize_branch_input "$manual_branch")"
  if [ -z "$manual_branch" ]; then
    exit 0
  fi
fi

if ! validate_branch_name "$manual_branch"; then
  die "invalid branch name: '$manual_branch'"
fi

existing_path="$(_comma_w_find_worktree_path_for_branch "$manual_branch" 2> /dev/null || true)"
if [ -n "$existing_path" ]; then
  info "Found existing worktree for branch '$manual_branch' at: $existing_path"
  _comma_w_issue_store_metadata "$existing_path" "$repo_name" "$issue_number" || true
  if [ "$focus_mode" -eq 1 ]; then
    "$(dirname "$0")/open.sh" -q "$existing_path"
  fi
  exit 0
fi

branch="$(with_issue_suffix "$manual_branch" "$issue_number")"
info "Issue #$issue_number -> branch: $branch"

default_branch="$(_comma_w_detect_default_branch)"

if _comma_w_branch_exists_locally_or_remote "$branch"; then
  # When a local branch exists but has no unique commits relative to the
  # default branch, it is a stale pointer left over from a previous worktree
  # session.  Fast-forward it so the recreated worktree starts from the
  # current default branch instead of a potentially months-old commit.
  if git show-ref --verify --quiet "refs/heads/$branch" 2> /dev/null; then
    _ff_target=""
    for _r in origin upstream; do
      if git show-ref --verify --quiet "refs/remotes/${_r}/${default_branch}" 2> /dev/null; then
        _ff_target="${_r}/${default_branch}"
        break
      fi
    done
    [ -n "$_ff_target" ] || _ff_target="$default_branch"
    _unique="$(git rev-list --count "${_ff_target}..${branch}" 2> /dev/null || echo 1)"
    if [ "$_unique" = "0" ]; then
      info "Branch has no unique commits; fast-forwarding to latest $default_branch"
      git branch -f "$branch" "$_ff_target" 2> /dev/null || true
    fi
  fi
  info "Branch already exists; creating/reusing worktree without base branch."
  if [ "$quiet_mode" -eq 1 ]; then
    "$(dirname "$0")/add.sh" --quiet "$branch"
  else
    "$(dirname "$0")/add.sh" "$branch"
  fi
else
  info "Creating new branch from base: $default_branch"
  if [ "$quiet_mode" -eq 1 ]; then
    "$(dirname "$0")/add.sh" --quiet "$branch" "$default_branch"
  else
    "$(dirname "$0")/add.sh" "$branch" "$default_branch"
  fi
fi

worktree_path="$(_comma_w_find_worktree_path_for_branch "$branch" 2> /dev/null || true)"
if [ -z "$worktree_path" ]; then
  die "failed to determine created worktree path for branch: $branch"
fi

_comma_w_issue_store_metadata "$worktree_path" "$repo_name" "$issue_number" || true

if [ "$focus_mode" -eq 1 ]; then
  "$(dirname "$0")/open.sh" -q "$worktree_path"
fi
