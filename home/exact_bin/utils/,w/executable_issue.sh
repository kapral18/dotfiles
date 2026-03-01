#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "$0")/../bash_utils_lib.sh"
source "$(dirname "$0")/../worktree_lib.sh"
source "$(dirname "$0")/issue_lib.sh"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required dependency: '$cmd'." >&2
    exit 1
  fi
}

show_usage() {
  cat <<'EOF'
Usage: ,w issue [-q|--quiet] [--focus] <issue_number|url>

Create or reuse a worktree for a GitHub issue.

This command:
- Finds an existing worktree for the issue (via per-worktree git config metadata) when available
- Otherwise creates a new branch + worktree and stores issue metadata in the worktree config

Options:
  -q, --quiet       Suppress informational output
  --focus           Switch/attach to the worktree's tmux session
  -h, --help        Show this help message

Notes:
  - Branch names are generated as: <type>/<scope>/<slug> where slug is 5-8 words.
  - If `ollama` (model: gemma3) is available, it is used to propose the slug and then strictly validated.
  - Issue metadata is stored per-worktree using git's worktree config mechanism.
EOF
}

quiet_mode=0
focus_mode=0

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

existing_path="$(_comma_w_issue_find_by_metadata "$repo_name" "$issue_number" 2>/dev/null || true)"
if [ -z "$existing_path" ]; then
  existing_path="$(_comma_w_issue_find_by_heuristics "$issue_number" 2>/dev/null || true)"
fi

if [ -n "$existing_path" ]; then
  info "Found existing issue worktree for #$issue_number at: $existing_path"
  _comma_w_issue_store_metadata "$existing_path" "$repo_name" "$issue_number" || true
  if [ "$focus_mode" -eq 1 ]; then
    "$(dirname "$0")/open.sh" -q "$existing_path"
  fi
  exit 0
fi

if ! IFS=$'\t' read -r issue_title issue_body < <(
  gh issue view "$issue_number" --json title,body --jq '[.title, (.body // "")] | @tsv' 2>/dev/null || true
); then
  die "failed to fetch issue #$issue_number metadata"
fi
if [ -z "$issue_title" ]; then
  die "issue #$issue_number has empty title (unexpected)"
fi

scope="$(_comma_w_issue_extract_scope "$issue_title")"
type="$(_comma_w_issue_infer_type "$issue_title")"

title_for_slug="$(_comma_w_issue_strip_scope "$issue_title")"

slug="$(_comma_w_issue_generate_slug_ollama "$scope" "$title_for_slug" "$issue_body" || true)"
if [ -z "$slug" ]; then
  slug="$(_comma_w_issue_words_to_kebab "$title_for_slug $issue_body")"
fi
slug="$(_comma_w_issue_slugify_kebab "$slug")"
if ! _comma_w_issue_validate_slug "$slug"; then
  die "failed to generate a valid 5-8 word slug for issue #$issue_number (got: '$slug')"
fi

# Guarantee uniqueness by appending the issue number (strip it first if ollama included it)
slug="${slug%-${issue_number}}"
branch="${type}/${scope}/${slug}-${issue_number}"
info "Issue #$issue_number -> branch: $branch"

default_branch="$(_comma_w_detect_default_branch)"

if _comma_w_branch_exists_locally_or_remote "$branch"; then
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

worktree_path="$(_comma_w_find_worktree_path_for_branch "$branch" 2>/dev/null || true)"
if [ -z "$worktree_path" ]; then
  die "failed to determine created worktree path for branch: $branch"
fi

_comma_w_issue_store_metadata "$worktree_path" "$repo_name" "$issue_number" || true

if [ "$focus_mode" -eq 1 ]; then
  "$(dirname "$0")/open.sh" -q "$worktree_path"
fi
