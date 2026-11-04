#!/usr/bin/env bash
# Description: Apply a patch file to multiple PRs

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$script_dir/../shared/bash_utils_lib.sh"

show_usage() {
  cat << 'EOF'
Usage: ,add-patch-to-prs <patch-file> [--message <msg>] [pr_numbers...] [--search <query>]

Apply a patch file to one or more PRs. If no PR numbers are given,
opens an fzf picker (with optional --search filter).

Arguments:
  patch-file          Path to the patch file to apply
  pr_numbers          One or more PR numbers (optional)

Options:
  -m, --message <msg> Commit message (default: "Apply patch <filename>")
  -s, --search <q>    Search query for fzf PR picker
  -h, --help          Show this help message
EOF
}

patch_file=""
commit_msg=""
search_query=""
pr_numbers=()

while [ $# -gt 0 ]; do
  case "$1" in
    -h | --help)
      show_usage
      exit 0
      ;;
    -m | --message)
      commit_msg="$2"
      shift 2
      ;;
    -s | --search)
      search_query="$2"
      shift 2
      ;;
    [0-9]*)
      pr_numbers+=("$1")
      shift
      ;;
    *)
      if [ -z "$patch_file" ]; then
        patch_file="$1"
      else
        echo "Error: unexpected argument '$1'" >&2
        show_usage
        exit 1
      fi
      shift
      ;;
  esac
done

if [ -z "$patch_file" ]; then
  echo "Error: patch file is required" >&2
  show_usage
  exit 1
fi

if [ ! -f "$patch_file" ]; then
  echo "Error: patch file not found: $patch_file" >&2
  exit 1
fi

patch_file="$(realpath "$patch_file")"
patch_basename="$(basename "$patch_file")"
: "${commit_msg:="Apply patch ${patch_basename}"}"

if [ ${#pr_numbers[@]} -eq 0 ]; then
  mapfile -t pr_numbers < <(gh pr list --search "${search_query:-}" --json number,title \
    --jq '.[] | "\(.number) \(.title)"' | fzf --multi --preview '
            gh pr view {1} --json number,title,body,author,labels,comments --template "
            # PR #{{.number}}: {{.title}}

            ---

            ## Author: {{.author.login}}

            {{range .labels}}- {{.name}} {{end}}

            ---

            {{.body}}
        ' | awk '{print $1}')
fi

if [ ${#pr_numbers[@]} -eq 0 ]; then
  echo "No PRs selected." >&2
  exit 0
fi

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "Working tree has uncommitted changes; commit or stash them first." >&2
  exit 1
fi

failed=()

for pr in "${pr_numbers[@]}"; do
  echo "Processing PR #$pr"

  if ! head_info=$(_safe_exec_cmd gh pr view "$pr" \
    --json headRefName,headRefOid,headRepository,headRepositoryOwner,url \
    --jq '[.headRefName, .headRefOid, .headRepository.name, .headRepositoryOwner.login, .url] | @tsv'); then
    failed+=("$pr")
    continue
  fi
  IFS=$'\t' read -r branch head_sha head_repo head_owner pr_url <<< "$head_info"
  if ! git check-ref-format "refs/heads/$branch" > /dev/null 2>&1 \
    || [[ ! "$head_sha" =~ ^[0-9a-f]{40,64}$ ]] \
    || [[ ! "$head_repo" =~ ^[A-Za-z0-9_.-]+$ ]] \
    || [[ ! "$head_owner" =~ ^[A-Za-z0-9_.-]+$ ]] \
    || [[ ! "$pr_url" =~ ^https://([A-Za-z0-9.-]+)/ ]]; then
    echo "Unable to resolve the head repository for PR #$pr" >&2
    failed+=("$pr")
    continue
  fi
  pr_host="${BASH_REMATCH[1]}"
  protocol="$(gh config get git_protocol --host "$pr_host" 2> /dev/null || true)"
  if [ "$protocol" = "ssh" ]; then
    head_url="git@${pr_host}:${head_owner}/${head_repo}.git"
  else
    head_url="https://${pr_host}/${head_owner}/${head_repo}.git"
  fi
  if ! _safe_exec_cmd git fetch --no-tags "$head_url" "refs/heads/$branch"; then
    failed+=("$pr")
    continue
  fi
  if [ "$(git rev-parse FETCH_HEAD)" != "$head_sha" ]; then
    echo "PR #$pr changed while resolving its head; skipping" >&2
    failed+=("$pr")
    continue
  fi
  checkout_parent="$(mktemp -d "${TMPDIR:-/tmp}/add-patch-pr-${pr}.XXXXXX")"
  checkout_path="$checkout_parent/worktree"
  if ! _safe_exec_cmd git worktree add --detach "$checkout_path" "$head_sha"; then
    rmdir "$checkout_parent" 2> /dev/null || true
    failed+=("$pr")
    continue
  fi
  if ! _safe_exec_cmd git -C "$checkout_path" apply --index "$patch_file"; then
    echo "Patch failed on PR #$pr, skipping" >&2
    git worktree remove --force "$checkout_path"
    rmdir "$checkout_parent"
    failed+=("$pr")
    continue
  fi
  if ! _safe_exec_cmd git -C "$checkout_path" commit -m "$commit_msg"; then
    git worktree remove --force "$checkout_path"
    rmdir "$checkout_parent"
    failed+=("$pr")
    continue
  fi
  if ! _safe_exec_cmd git -C "$checkout_path" push "$head_url" "HEAD:refs/heads/$branch"; then
    recovery_branch="patch-pr-${pr}-${checkout_parent##*/}"
    if git branch "$recovery_branch" "$(git -C "$checkout_path" rev-parse HEAD)"; then
      echo "Push failed on PR #$pr; the commit stays on local branch $recovery_branch" >&2
      git worktree remove "$checkout_path"
      rmdir "$checkout_parent"
    else
      echo "Push failed on PR #$pr; recovery checkout: $checkout_path" >&2
    fi
    failed+=("$pr")
    continue
  fi
  git worktree remove "$checkout_path"
  rmdir "$checkout_parent"
  echo "Finished processing PR #$pr"

  if [ -t 0 ]; then
    read -r -p "Press enter to continue..."
  fi
done

if [ ${#failed[@]} -gt 0 ]; then
  echo "Failed PRs: ${failed[*]}" >&2
  exit 1
fi
