#!/usr/bin/env bash
# Batch worktree creation for the GitHub picker.
# Accepts one or more TSV lines (from fzf selection file).
# PRs: creates worktrees automatically (branch comes from the PR).
# Issues: opens $EDITOR with a batch naming buffer, then creates worktrees.
#
# Usage: gh_batch_worktree.sh <selection_file> [--background]
#
# The selection file contains one TSV line per selected item.
# Each line has fields: display\tkind\trepo_nwo\tnumber\turl\t...
set -euo pipefail

PATH="$HOME/bin:$PATH"
EDITOR="${EDITOR:-nvim}"

die() {
  printf 'gh_batch_worktree: %s\n' "$*" >&2
  exit 1
}

selection_file="${1:-}"
background=0
[ "${2:-}" = "--background" ] && background=1

[ -n "$selection_file" ] && [ -f "$selection_file" ] || die "missing or invalid selection file"

prs=()
pr_repos=()
issues=()
issue_repos=()
issue_titles=()

while IFS=$'\t' read -r _display kind repo num _rest; do
  [ -n "$kind" ] && [ -n "$repo" ] && [ -n "$num" ] || continue
  [ "$kind" = "header" ] && continue
  case "$kind" in
    pr)
      prs+=("$num")
      pr_repos+=("$repo")
      ;;
    issue)
      issues+=("$num")
      issue_repos+=("$repo")
      title="$(gh issue view "$num" -R "$repo" --json title --jq .title 2> /dev/null || echo "")"
      issue_titles+=("$title")
      ;;
  esac
done < "$selection_file"

resolve_repo_path() {
  local nwo="$1"
  local owner="${nwo%%/*}"
  local repo="${nwo#*/}"
  local parent=""
  if [ "$owner" = "elastic" ]; then
    parent="$HOME/work"
  else
    parent="$HOME/code"
  fi
  local wrapper="$parent/$repo"
  if [ -d "$wrapper" ]; then
    for d in main master dev develop trunk; do
      if [ -e "$wrapper/$d/.git" ]; then
        printf '%s\n' "$wrapper/$d"
        return 0
      fi
    done
    if [ -e "$wrapper/.git" ]; then
      printf '%s\n' "$wrapper"
      return 0
    fi
    local child_git
    for child_git in "$wrapper"/*/.git; do
      [ -e "$child_git" ] || continue
      printf '%s\n' "$(dirname "$child_git")"
      return 0
    done
  fi
  printf '%s\n' "$wrapper"
}

issue_branches=()

if [ ${#issues[@]} -gt 0 ]; then
  tmpfile="$(mktemp /tmp/gh_batch_worktree_XXXXXX.md)"
  trap 'rm -f "$tmpfile"' EXIT

  {
    printf '# Branch names for issue worktrees\n'
    printf '# Format: <number>|<branch-name>  (empty branch = skip)\n'
    printf '# Branch will be created as: <branch-name>-<number>\n'
    printf '#\n'
    for i in "${!issues[@]}"; do
      printf '# %s — %s (%s)\n' "${issues[$i]}" "${issue_titles[$i]}" "${issue_repos[$i]}"
      printf '%s|\n' "${issues[$i]}"
    done
  } > "$tmpfile"

  $EDITOR "$tmpfile"

  while IFS='|' read -r num branch; do
    [ -n "$num" ] || continue
    [[ "$num" =~ ^# ]] && continue
    num="$(printf '%s' "$num" | tr -d '[:space:]')"
    branch="$(printf '%s' "$branch" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    issue_branches+=("${num}:${branch}")
  done < "$tmpfile"
fi

created=0
skipped=0
failed=0

_create_pr_worktree() {
  local repo="$1" num="$2"
  local repo_path
  repo_path="$(resolve_repo_path "$repo")"
  if [ ! -d "$repo_path" ] || [ ! -e "$repo_path/.git" ]; then
    printf 'SKIP PR #%s — repo not found: %s\n' "$num" "$repo_path"
    skipped=$((skipped + 1))
    return
  fi
  if (cd "$repo_path" && ,w prs -q "$num") 2> /dev/null; then
    printf 'OK   PR #%s (%s)\n' "$num" "$repo"
    created=$((created + 1))
  else
    printf 'FAIL PR #%s (%s)\n' "$num" "$repo"
    failed=$((failed + 1))
  fi
}

_create_issue_worktree() {
  local repo="$1" num="$2" branch="$3"
  if [ -z "$branch" ]; then
    printf 'SKIP issue #%s — no branch name\n' "$num"
    skipped=$((skipped + 1))
    return
  fi
  local repo_path
  repo_path="$(resolve_repo_path "$repo")"
  if [ ! -d "$repo_path" ] || [ ! -e "$repo_path/.git" ]; then
    printf 'SKIP issue #%s — repo not found: %s\n' "$num" "$repo_path"
    skipped=$((skipped + 1))
    return
  fi
  if (cd "$repo_path" && ,w issue -q -b "$branch" "$num") 2> /dev/null; then
    printf 'OK   issue #%s → %s\n' "$num" "$branch"
    created=$((created + 1))
  else
    printf 'FAIL issue #%s → %s\n' "$num" "$branch"
    failed=$((failed + 1))
  fi
}

for i in "${!prs[@]}"; do
  _create_pr_worktree "${pr_repos[$i]}" "${prs[$i]}"
done

for entry in "${issue_branches[@]+"${issue_branches[@]}"}"; do
  num="${entry%%:*}"
  branch="${entry#*:}"
  for i in "${!issues[@]}"; do
    if [ "${issues[$i]}" = "$num" ]; then
      _create_issue_worktree "${issue_repos[$i]}" "$num" "$branch"
      break
    fi
  done
done

printf '\nDone: %d created, %d skipped, %d failed\n' "$created" "$skipped" "$failed"

if [ "$background" -eq 0 ]; then
  printf '\nPress any key to continue...'
  read -r -n 1
fi
