#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$script_dir/../shared/worktree_lib.sh"

usage() {
  cat << 'EOF'
Usage:
  ,gh-tfork <owner/repo>

Behavior:
  - Forks <owner/repo> using GitHub CLI.
  - Clones into ~/code/<repo>/<default-branch>.
  - Creates (or focuses) a herdr workspace named <wrapper/repo>|<default-branch>.
  - Workspace layout: 2 tabs, each with 2 panes side by side.
EOF
}

if [[ "${1:-}" = "-h" || "${1:-}" = "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 2
fi

repo_spec="$1"

if [[ ! "$repo_spec" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]]; then
  echo "Error: expected <owner/repo>, got: $repo_spec" >&2
  exit 2
fi

command -v gh > /dev/null 2>&1 || {
  echo "Error: 'gh' is required." >&2
  exit 1
}
command -v git > /dev/null 2>&1 || {
  echo "Error: 'git' is required." >&2
  exit 1
}

repo_owner="${repo_spec%%/*}"
repo_name="${repo_spec##*/}"

parent_dir="$HOME/code"
mkdir -p "$parent_dir"
cd "$parent_dir"

repo_wrapper_path="$(pwd -P)/${repo_name}"

if [[ -e "$repo_wrapper_path" ]]; then
  echo "Error: repo directory already exists: $repo_wrapper_path" >&2
  exit 1
fi

gh_login="$(gh api user --jq '.login' 2> /dev/null || true)"
if [ -z "$gh_login" ]; then
  echo "Error: failed to determine GitHub login via 'gh api user'." >&2
  exit 1
fi

git_protocol="$(gh config get git_protocol 2> /dev/null || true)"
if [ -z "$git_protocol" ]; then
  git_protocol="https"
fi

remote_url_for_repo() {
  local owner_repo="$1"
  if [ "$git_protocol" = "ssh" ]; then
    printf 'git@github.com:%s.git\n' "$owner_repo"
  else
    printf 'https://github.com/%s.git\n' "$owner_repo"
  fi
}

# Prints "true" when fork_repo is a fork of upstream_repo, "false" when it is another repo, nothing when missing.
fork_parent_matches() {
  local upstream_repo="$1"
  local fork_repo="$2"
  gh api "repos/${fork_repo}" --jq "(.fork and ((.parent.full_name // \"\") | ascii_downcase) == (\"${upstream_repo}\" | ascii_downcase))" 2> /dev/null || true
}

ensure_fork_exists() {
  local upstream_repo="$1"
  local fork_repo="$2"

  case "$(fork_parent_matches "$upstream_repo" "$fork_repo")" in
    true) return 0 ;;
    false)
      echo "Error: ${fork_repo} exists but is not a fork of ${upstream_repo}." >&2
      exit 1
      ;;
  esac

  # Fork creation is async; 202 is expected for new forks.
  gh api -X POST "repos/${upstream_repo}/forks" > /dev/null 2>&1 || true

  local i
  for i in $(seq 1 45); do
    if [ "$(fork_parent_matches "$upstream_repo" "$fork_repo")" = true ]; then
      return 0
    fi
    sleep 2
  done

  echo "Error: fork did not become available in time: ${fork_repo}" >&2
  exit 1
}

clone_owner="$gh_login"
if [ "$repo_owner" = "$gh_login" ]; then
  clone_owner="$repo_owner"
else
  ensure_fork_exists "$repo_spec" "${gh_login}/${repo_name}"
fi

clone_repo="${clone_owner}/${repo_name}"
clone_url="$(remote_url_for_repo "$clone_repo")"
git clone "$clone_url" "$repo_name"

if [ "$clone_owner" != "$repo_owner" ]; then
  upstream_url="$(remote_url_for_repo "$repo_spec")"
  if ! git -C "$repo_name" remote get-url upstream > /dev/null 2>&1; then
    git -C "$repo_name" remote add upstream "$upstream_url"
  fi
fi

detect_branch_name() {
  local repo_dir="$1"
  local branch=""

  branch="$(git -C "$repo_dir" symbolic-ref --quiet --short HEAD 2> /dev/null || true)"
  if [ -n "$branch" ]; then
    printf '%s\n' "$branch"
    return 0
  fi

  branch="$(git -C "$repo_dir" symbolic-ref -q --short refs/remotes/origin/HEAD 2> /dev/null || true)"
  if [ -n "$branch" ]; then
    printf '%s\n' "${branch#origin/}"
    return 0
  fi

  branch="$(git -C "$repo_dir" symbolic-ref -q --short refs/remotes/upstream/HEAD 2> /dev/null || true)"
  if [ -n "$branch" ]; then
    printf '%s\n' "${branch#upstream/}"
    return 0
  fi

  printf '%s\n' "main"
}

branch_name="$(detect_branch_name "$repo_name")"
clone_dir="${repo_name}/${branch_name}"
clone_path="$(pwd -P)/${clone_dir}"
parent_name="$(_comma_w_parent_name_from_dir "$repo_wrapper_path")"
session_name="$(_comma_w_workspace_name "$parent_name" "$branch_name")"

if [[ -e "$clone_dir/.git" ]]; then
  :
elif [[ -e "$repo_name/.git" ]]; then
  tmp_dir="${repo_name}.tmp.$$"
  mv "$repo_name" "$tmp_dir"
  mkdir -p "$(dirname "$clone_dir")"
  mv "$tmp_dir" "$clone_dir"
else
  echo "Error: unable to locate cloned repository for $repo_spec" >&2
  exit 1
fi

command -v herdr > /dev/null 2>&1 || {
  echo "Warning: 'herdr' is not available; skipping workspace creation." >&2
  exit 0
}

if _comma_w_herdr workspace list > /dev/null 2>&1 && [ -z "$(_comma_w_workspace_id_by_label "$session_name")" ]; then
  created="$(_comma_w_herdr workspace create --cwd "$clone_path" --label "$session_name" --no-focus)"
  ws_id="$(jq -r '.result.workspace.workspace_id' <<< "$created")"
  _comma_w_record_workspace_path "$ws_id" "$session_name" "$clone_path"
  _comma_w_herdr tab rename "$(jq -r '.result.tab.tab_id' <<< "$created")" "$branch_name" > /dev/null
  _comma_w_herdr pane split "$(jq -r '.result.root_pane.pane_id' <<< "$created")" --direction right --cwd "$clone_path" --no-focus > /dev/null

  shell_tab="$(_comma_w_herdr tab create --workspace "$ws_id" --cwd "$clone_path" --label shell --no-focus)"
  _comma_w_herdr pane split "$(jq -r '.result.root_pane.pane_id' <<< "$shell_tab")" --direction right --cwd "$clone_path" --no-focus > /dev/null
fi

_comma_w_focus_workspace 0 "$session_name" "$clone_path"
