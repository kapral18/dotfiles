#!/usr/bin/env bash
# Batch worktree creation for the GitHub picker.
# Accepts one or more TSV lines (from fzf selection file).
# PRs: creates worktrees automatically (branch comes from the PR).
# Issues: opens $EDITOR with a naming buffer, then creates worktrees.
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

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
mkdir -p "$cache_dir" 2> /dev/null || true

selection_file=""
background=0
branches_file=""

while [ $# -gt 0 ]; do
  case "$1" in
    --background)
      background=1
      shift
      ;;
    --branches-file)
      [ $# -ge 2 ] || die "missing value for --branches-file"
      branches_file="$2"
      shift 2
      ;;
    -*)
      die "unknown flag: $1"
      ;;
    *)
      if [ -z "$selection_file" ]; then
        selection_file="$1"
      fi
      shift
      ;;
  esac
done

[ -n "$selection_file" ] && [ -f "$selection_file" ] || die "missing or invalid selection file"

# Background mode is the last consumer of `$selection_file` (a per-binding
# snapshot minted by gh_picker_ctrl_t.sh / gh_picker_enter.sh). Foreground
# mode hands the snapshot off to background mode via `tmux run-shell -b`, so
# only the background pass should unlink it on exit. The branches buffer is
# foreground-owned and unlinked with its own trap below.
if [ "$background" -eq 1 ]; then
  trap 'rm -f "$selection_file" "${branches_file:-}" 2>/dev/null || true' EXIT
fi

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
      if [ "$background" -eq 0 ]; then
        title="$(gh issue view "$num" -R "$repo" --json title --jq .title 2> /dev/null || echo "")"
      else
        title=""
      fi
      issue_titles+=("$title")
      ;;
  esac
done < "$selection_file"

issue_branches=()

if [ "$background" -eq 0 ]; then
  # Foreground: collect issue branch names (if any), then dispatch everything to background.
  if [ ${#issues[@]} -gt 0 ]; then
    tmpfile="$(mktemp /tmp/gh_batch_worktree_XXXXXX.conf)"
    trap 'rm -f "$tmpfile"' EXIT

    {
      printf '# Branch names for issue worktrees\n'
      printf '# Format: <number>|<branch-name>  (empty branch = skip)\n'
      printf '# Branch will be created as: <branch-name>-<number>\n'
      printf '# Tip: do NOT include tmux/session prefixes like work/kibana|...; just use the branch name (e.g. chore/foo)\n'
      printf '#\n'
      for i in "${!issues[@]}"; do
        printf '# %s — %s (%s)\n' "${issues[$i]}" "${issue_titles[$i]}" "${issue_repos[$i]}"
        printf '%s|\n' "${issues[$i]}"
      done
    } > "$tmpfile"

    $EDITOR "$tmpfile"

    branches_file="$(mktemp "${cache_dir}/gh_batch_worktree_branches_XXXXXX.conf")"
    # If we crash between `mktemp` and the background dispatch, we'd leak the
    # branches file. The trap is replaced once the background process owns it
    # (the dispatch line below).
    trap 'rm -f "$tmpfile" "$branches_file" 2>/dev/null || true' EXIT
    cp "$tmpfile" "$branches_file" 2> /dev/null || die "failed to persist branches file"

    tmux run-shell -b "$(printf %q "$0") $(printf %q "$selection_file") --background --branches-file $(printf %q "$branches_file")" \
      2> /dev/null || true
    # Background mode owns `$branches_file` and `$selection_file` from here.
    trap 'rm -f "$tmpfile" 2>/dev/null || true' EXIT
  else
    tmux run-shell -b "$(printf %q "$0") $(printf %q "$selection_file") --background" \
      2> /dev/null || true
  fi
  exit 0
fi

if [ ${#issues[@]} -gt 0 ] && [ -n "$branches_file" ] && [ -f "$branches_file" ]; then
  while IFS='|' read -r num branch; do
    [ -n "$num" ] || continue
    [[ "$num" =~ ^# ]] && continue
    num="$(printf '%s' "$num" | tr -d '[:space:]')"
    branch="$(printf '%s' "$branch" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    issue_branches+=("${num}:${branch}")
  done < "$branches_file"
fi

# Per-item outcome counters. They drive nothing user-visible on their own: all
# feedback is delivered through the dashboard markers (amber ◌ in-progress,
# cyan ◆ done, cleared on skip/fail). The batch run prints nothing to its pane.
created=0
skipped=0
failed=0

# `tmux run-shell -b` runs the background pass in a pane and surfaces its
# stdout/stderr there. Keep that pane silent — redirect both streams to
# /dev/null so the only feedback is the in-dashboard markers.
exec > /dev/null 2>&1

_notify_fzf_reload() {
  local mode scope port items_cmd cache_load_cmd
  mode="$(cat "${cache_dir}/gh_picker_mode" 2> /dev/null || echo work)"
  scope="$(cat "${cache_dir}/gh_picker_scope" 2> /dev/null || echo all)"
  port="$(cat "${cache_dir}/gh_picker_port" 2> /dev/null || true)"
  [ -n "$port" ] || return 0
  items_cmd="$HOME/.config/tmux/scripts/pickers/github/gh_items.sh"
  cache_load_cmd="GH_PICKER_MODE=$(printf %q "$mode") GH_PICKER_SCOPE=$(printf %q "$scope") $(printf %q "$items_cmd") --cache-only 2>/dev/null"
  # Use IPv4 explicitly; on macOS `localhost` may resolve to ::1 while fzf binds 127.0.0.1.
  # Fire-and-forget: backgrounded so the per-item progress feedback never adds
  # latency to the batch loop (curl roundtrip + 1s timeout for stale ports
  # would otherwise serialize against `,w prs/issue` work). Reloads are
  # idempotent re-reads of the cache file, so out-of-order arrival is safe.
  # The subshell breaks the parent-child relationship so the script can exit
  # without `wait`-ing on stragglers.
  (curl -s --max-time 1 -XPOST "http://127.0.0.1:${port}" -d "reload($cache_load_cmd)+track" > /dev/null 2>&1 &) 2> /dev/null
}

_patch_cache_entry() {
  local kind="$1" repo="$2" num="$3" state="${4:-done}"
  local mode cache_file script_dir patcher
  mode="$(cat "${cache_dir}/gh_picker_mode" 2> /dev/null || echo work)"
  cache_file="${cache_dir}/gh_picker_${mode}.tsv"
  script_dir="$HOME/.config/tmux/scripts/pickers/github"
  patcher="${script_dir}/lib/gh_patch_picker_cache.py"
  if [ -f "$patcher" ] && [ -f "$cache_file" ]; then
    python3 -u "$patcher" --cache-file "$cache_file" --kind "$kind" --repo "$repo" --num "$num" --state "$state" 2> /dev/null || true
  fi
}

# Mark an item as in-progress (amber ◌) and re-render so the user sees a
# loading marker the instant creation for that item starts.
_mark_loading() {
  local kind="$1" repo="$2" num="$3"
  _patch_cache_entry "$kind" "$repo" "$num" loading
  _notify_fzf_reload
}

_create_pr_worktree() {
  local repo="$1" num="$2"
  _mark_loading "pr" "$repo" "$num"
  if ! ,gh-worktree pr "$repo" "$num" --print-root --no-bootstrap > /dev/null 2>&1; then
    skipped=$((skipped + 1))
    _patch_cache_entry "pr" "$repo" "$num" clear
    _notify_fzf_reload
    return
  fi
  if ,gh-worktree pr "$repo" "$num" --quiet --no-bootstrap 2> /dev/null; then
    created=$((created + 1))
    _patch_cache_entry "pr" "$repo" "$num" "done"
    # Progressive feedback: re-render fzf so the ◆ marker for this item appears
    # immediately, instead of waiting for the whole batch to finish.
    _notify_fzf_reload
  else
    failed=$((failed + 1))
    _patch_cache_entry "pr" "$repo" "$num" clear
    _notify_fzf_reload
  fi
}

_create_issue_worktree() {
  local repo="$1" num="$2" branch="$3"
  if [ -z "$branch" ]; then
    skipped=$((skipped + 1))
    return
  fi
  _mark_loading "issue" "$repo" "$num"
  if ! ,gh-worktree issue "$repo" "$num" --print-root --no-bootstrap --branch "$branch" > /dev/null 2>&1; then
    skipped=$((skipped + 1))
    _patch_cache_entry "issue" "$repo" "$num" clear
    _notify_fzf_reload
    return
  fi
  if ,gh-worktree issue "$repo" "$num" --quiet --branch "$branch" --no-bootstrap 2> /dev/null; then
    created=$((created + 1))
    _patch_cache_entry "issue" "$repo" "$num" "done"
    # Progressive feedback: re-render fzf so the ◆ marker for this item appears
    # immediately, instead of waiting for the whole batch to finish.
    _notify_fzf_reload
  else
    failed=$((failed + 1))
    _patch_cache_entry "issue" "$repo" "$num" clear
    _notify_fzf_reload
  fi
}

# Create each marked worktree. All progress + outcome feedback is delivered
# through the dashboard markers via `_patch_cache_entry` + `_notify_fzf_reload`
# inside these helpers — the batch run itself prints nothing.
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
