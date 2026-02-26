#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "$0")/../bash_utils_lib.sh"

show_usage() {
  cat <<EOF
Usage: ,w ls [--porcelain] [--selectable] [--long] [--dirty] [--full-path] [--no-header] [--no-column] [--sort branch|path]

List git worktrees.

Options:
  --porcelain        Print raw \`git worktree list --porcelain\` output
  --selectable       Print \`branch<TAB>path\` for non-detached, non-locked worktrees
  --long             Include ahead/behind columns
  --dirty            Compute and show dirty state (slow in large repos)
  --full-path        Do not shorten paths relative to the worktree parent
  --no-header        Omit table header (default output only)
  --no-column        Do not align output with \`column\`
  --sort branch|path Sort rows (default: branch)
  -h, --help         Show this help message
EOF
}

porcelain=0
selectable=0
long_mode=0
dirty_mode=0
full_path=0
no_header=0
no_column=0
sort_mode="branch"

while [ $# -gt 0 ]; do
  case "$1" in
  -h | --help)
    show_usage
    exit 0
    ;;
  --porcelain)
    porcelain=1
    shift
    ;;
  --selectable)
    selectable=1
    shift
    ;;
  --long)
    long_mode=1
    shift
    ;;
  --dirty)
    dirty_mode=1
    shift
    ;;
  --full-path)
    full_path=1
    shift
    ;;
  --no-header)
    no_header=1
    shift
    ;;
  --no-column)
    no_column=1
    shift
    ;;
  --sort)
    if [ $# -lt 2 ]; then
      show_usage
      exit 1
    fi
    sort_mode="$2"
    shift 2
    ;;
  *)
    echo "Error: Unknown option '$1'" >&2
    show_usage
    exit 1
    ;;
  esac
done

if [ "$porcelain" -eq 1 ]; then
  exec git worktree list --porcelain
fi

case "$sort_mode" in
branch | path) ;;
*)
  echo "Error: invalid --sort '$sort_mode' (use: branch|path)." >&2
  exit 1
  ;;
esac

line=""
key=""
value=""

worktree_path=""
branch_ref=""
head_sha=""
detached=0
locked=0

parent_dir=$(_get_worktree_parent_dir)
parent_name=$(basename "$parent_dir")
pwd_path="$PWD"
default_branch="$(git config --get init.defaultbranch 2>/dev/null || echo "main")"

tmux_sessions_file=""
tmux_sessions=()
if [ "$selectable" -eq 0 ] && command -v tmux >/dev/null 2>&1; then
  while IFS= read -r session; do
    [ -z "$session" ] && continue
    tmux_sessions+=("$session")
  done < <(tmux list-sessions -F '#{session_name}' 2>/dev/null || true)
fi

relpath_for() {
  local p="$1"
  if [ "$full_path" -eq 1 ]; then
    printf '%s\n' "$p"
    return 0
  fi
  case "$p" in
  "$parent_dir"/*)
    printf '%s\n' "${p#"$parent_dir"/}"
    ;;
  *)
    printf '%s\n' "$p"
    ;;
  esac
}

is_current() {
  local p="$1"
  case "$pwd_path" in
  "$p") return 0 ;;
  "$p"/*) return 0 ;;
  esac
  return 1
}

upstream_branches=()
upstream_values=()
if [ "$selectable" -eq 0 ]; then
  tab_char=$'\t'
  while IFS=$'\t' read -r branch upstream; do
    [ -z "$branch" ] && continue
    if [ -z "$upstream" ] || [ "$upstream" = "." ]; then
      upstream="-"
    fi
    upstream_branches+=("$branch")
    upstream_values+=("$upstream")
  done < <(git for-each-ref --format="%(refname:short)${tab_char}%(upstream:short)" refs/heads 2>/dev/null || true)
fi

upstream_for_branch() {
  local branch="$1"
  local i
  for i in "${!upstream_branches[@]}"; do
    if [ "${upstream_branches[$i]}" = "$branch" ]; then
      printf '%s\n' "${upstream_values[$i]}"
      return 0
    fi
  done
  printf '%s\n' "-"
}

ahead_behind_for() {
  local left="$1"
  local right="$2"
  local counts
  counts="$(git rev-list --left-right --count "${left}...${right}" 2>/dev/null || true)"
  if [ -z "$counts" ]; then
    printf '%s\t%s\n' "-" "-"
    return 0
  fi
  printf '%s\n' "$counts" | awk '{print $1 "\t" $2}'
}

tmux_has_session_for_branch() {
  local branch="$1"
  if [ ${#tmux_sessions[@]} -eq 0 ]; then
    printf '%s\n' "-"
    return 0
  fi
  local session_name
  session_name="${parent_name}|${branch}"
  local s
  for s in "${tmux_sessions[@]}"; do
    if [ "$s" = "$session_name" ]; then
      printf '%s\n' "+"
      return 0
    fi
  done
  printf '%s\n' "-"
}

dirty_for_path() {
  local p="$1"
  if [ "$dirty_mode" -eq 0 ]; then
    printf '%s\n' "-"
    return 0
  fi

  if [ ! -d "$p" ]; then
    printf '%s\n' "?"
    return 0
  fi

  if [ ! -e "$p/.git" ]; then
    printf '%s\n' "?"
    return 0
  fi

  if IFS= read -r -d '' _ < <(GIT_OPTIONAL_LOCKS=0 git -C "$p" status --porcelain=v1 -uno -z 2>/dev/null); then
    printf '%s\n' "!"
    return 0
  fi

  printf '%s\n' "-"
}

emit() {
  if [ -z "$worktree_path" ]; then
    return 0
  fi

  if [ "$selectable" -eq 1 ]; then
    if [ "$detached" -eq 1 ] || [ "$locked" -eq 1 ]; then
      return 0
    fi
    if [[ "$branch_ref" != refs/heads/* ]]; then
      return 0
    fi
    branch="${branch_ref#refs/heads/}"
    printf '%s\t%s\n' "$branch" "$worktree_path"
    return 0
  fi

  cur=" "
  if is_current "$worktree_path"; then
    cur="*"
  fi

  branch_display="(none)"
  branch=""
  if [[ "$branch_ref" == refs/heads/* ]]; then
    branch_display="${branch_ref#refs/heads/}"
    branch="$branch_display"
  elif [ -n "$branch_ref" ]; then
    branch_display="$branch_ref"
  elif [ "$detached" -eq 1 ] && [ -n "$head_sha" ]; then
    branch_display="@${head_sha:0:8}"
  fi

  prio=2
  if [ "$cur" = "*" ]; then
    prio=0
  elif [ -n "$branch" ] && [ "$branch" = "$default_branch" ]; then
    prio=1
  elif [ "$detached" -eq 1 ] || [ -z "$branch" ]; then
    prio=3
  fi

  flags=""
  if [ "$detached" -eq 1 ]; then
    if [ -n "$head_sha" ]; then
      flags="${flags}detached@${head_sha:0:8} "
    else
      flags="${flags}detached "
    fi
  fi
  if [ "$locked" -eq 1 ]; then
    flags="${flags}locked "
  fi
  if [ ! -e "$worktree_path" ]; then
    prio=4
    flags="${flags}missing "
  fi
  flags="${flags%% }"

  display_path="$(relpath_for "$worktree_path")"
  dirty_col="$(dirty_for_path "$worktree_path")"
  state="${flags:--}"

  upstream="-"
  ahead="-"
  behind="-"
  tmux_col="-"

  if [ -n "$branch" ]; then
    upstream="$(upstream_for_branch "$branch")"
    tmux_col="$(tmux_has_session_for_branch "$branch")"
    if [ "$long_mode" -eq 1 ] && [ "$upstream" != "-" ]; then
      IFS=$'\t' read -r ahead behind < <(ahead_behind_for "$branch" "$upstream")
    fi
  fi

  # Always emit the superset columns:
  # prio CUR BRANCH PATH UPSTREAM AHEAD BEHIND DIRTY TMUX STATE
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$prio" "$cur" "$branch_display" "$display_path" "$upstream" "$ahead" "$behind" "$dirty_col" "$tmux_col" "$state"
}

rows_file="$(mktemp -t ,w-ls-rows.XXXXXX)"
cleanup() {
  rm -f "$rows_file" || true
}
trap cleanup EXIT

while IFS= read -r line; do
  key="${line%% *}"
  value="${line#* }"

  case "$key" in
  worktree)
    emit >>"$rows_file"
    worktree_path="$value"
    branch_ref=""
    head_sha=""
    detached=0
    locked=0
    ;;
  HEAD)
    head_sha="$value"
    ;;
  branch)
    branch_ref="$value"
    ;;
  detached)
    detached=1
    ;;
  locked)
    locked=1
    ;;
  esac
done < <(git worktree list --porcelain)
emit >>"$rows_file"

sorted_file="$(mktemp -t ,w-ls-sorted.XXXXXX)"
trap 'rm -f "$sorted_file" || true; cleanup' EXIT

if [ "$selectable" -eq 1 ]; then
  if [ "$sort_mode" = "path" ]; then
    sort -t $'\t' -k 2,2 "$rows_file" >"$sorted_file"
  else
    sort -t $'\t' -k 1,1 "$rows_file" >"$sorted_file"
  fi
  cat "$sorted_file"
  exit 0
fi

if [ "$sort_mode" = "path" ]; then
  sort_key=4
else
  sort_key=3
fi
sort -t $'\t' -k 1,1n -k "${sort_key},${sort_key}" "$rows_file" >"$sorted_file"

output_file="$(mktemp -t ,w-ls-out.XXXXXX)"
trap 'rm -f "$output_file" || true; rm -f "$sorted_file" || true; cleanup' EXIT

{
  if [ "$no_header" -eq 0 ]; then
    if [ "$long_mode" -eq 1 ]; then
      if [ "$dirty_mode" -eq 1 ]; then
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "CUR" "BRANCH" "PATH" "UPSTREAM" "AHEAD" "BEHIND" "DIRTY" "TMUX" "STATE"
      else
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "CUR" "BRANCH" "PATH" "UPSTREAM" "AHEAD" "BEHIND" "TMUX" "STATE"
      fi
    else
      if [ "$dirty_mode" -eq 1 ]; then
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "CUR" "BRANCH" "PATH" "UPSTREAM" "DIRTY" "TMUX" "STATE"
      else
        printf '%s\t%s\t%s\t%s\t%s\t%s\n' "CUR" "BRANCH" "PATH" "UPSTREAM" "TMUX" "STATE"
      fi
    fi
  fi
  if [ "$long_mode" -eq 1 ]; then
    if [ "$dirty_mode" -eq 1 ]; then
      cut -f 2,3,4,5,6,7,8,9,10 "$sorted_file"
    else
      cut -f 2,3,4,5,6,7,9,10 "$sorted_file"
    fi
  else
    if [ "$dirty_mode" -eq 1 ]; then
      cut -f 2,3,4,5,8,9,10 "$sorted_file"
    else
      cut -f 2,3,4,5,9,10 "$sorted_file"
    fi
  fi
} >"$output_file"

if [ "$no_column" -eq 0 ] && command -v column >/dev/null 2>&1 && [ -t 1 ]; then
  column -t -s $'\t' <"$output_file"
else
  cat "$output_file"
fi
