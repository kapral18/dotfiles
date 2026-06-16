#!/usr/bin/env bash
# Inline command palette for the GitHub picker.
#
# Wired to `alt-x`. Called as:
#   gh_picker_palette.sh <items_file> <mode_file> <scope_file> <items_cmd>
#
# Where <items_file> is fzf's `{+f}` — one tab-delimited line per selected or
# cursor item. The orchestrator parses (kind, repo, num) per row, opens a
# fzf-in-fzf verb menu, prompts for any required arguments, then dispatches
# to `gh_palette_verbs.py` once per applicable item. It marks selected rows
# while mutations run, then refreshes the outer picker in the background.
set -euo pipefail

items_file="${1:-}"
mode_file="${2:-}"
scope_file="${3:-}"
items_cmd="${4:-}"

if [ -z "$items_file" ] || [ -z "$mode_file" ] || [ -z "$scope_file" ] || [ -z "$items_cmd" ]; then
  exit 0
fi
[ -f "$items_file" ] || exit 0

cleanup_files=()
cleanup() {
  local f
  for f in "${cleanup_files[@]+"${cleanup_files[@]}"}"; do
    [ -n "$f" ] || continue
    rm -f "$f" 2> /dev/null || true
  done
}
trap cleanup EXIT

script_dir="$(cd "$(dirname "$0")" && pwd)"
verbs_helper="$script_dir/gh_palette_verbs.py"
row_loader_lib="$script_dir/gh_row_loader.sh"
if [ -f "$row_loader_lib" ]; then
  # shellcheck source=/dev/null
  . "$row_loader_lib"
fi

mode="$(cat "$mode_file" 2> /dev/null || echo work)"
scope="$(cat "$scope_file" 2> /dev/null || echo all)"
row_loader_targets_file=""
row_loader_pid=""

# Parse selected/cursor items. Each line is the full picker TSV row, so cols
# 2/3/4 are kind/repo/num. Skip header rows (cols 2 == "header").
declare -a kinds=() repos=() nums=()
while IFS=$'\t' read -r _disp kind repo num _rest; do
  if [ "$kind" = "pr" ] || [ "$kind" = "issue" ]; then
    kinds+=("$kind")
    repos+=("$repo")
    nums+=("$num")
  fi
done < "$items_file"

count="${#kinds[@]}"
if [ "$count" -eq 0 ]; then
  tmux display-message "palette: no PR or issue under cursor" 2> /dev/null || true
  exit 0
fi

multi=0
[ "$count" -gt 1 ] && multi=1

# Verb list. Columns: id|label|kinds|multi where kinds is csv of pr/issue and
# multi is 1 if the verb supports a multi-selection loop.
verbs=$(
  cat << 'VERBS'
close|close (optional reason for issues)|pr,issue|1
reopen|reopen|pr,issue|1
approve|approve PR|pr|0
request-changes|request changes on PR (body required)|pr|0
merge|merge PR (default method, with confirm)|pr|0
label-add|add label|pr,issue|1
label-rm|remove label|pr,issue|1
comment|comment (single-line body)|pr,issue|1
rr|request review (PR only)|pr|0
VERBS
)

# Filter the verb list to what applies to the current selection. If multi, drop
# verbs that don't support multi. If the selection has any issue, drop pr-only
# verbs; if any pr, drop issue-only verbs. (Today all single-kind verbs are
# PR-only, but the filter handles both axes for future-proofing.)
has_pr=0
has_issue=0
for k in "${kinds[@]}"; do
  [ "$k" = "pr" ] && has_pr=1
  [ "$k" = "issue" ] && has_issue=1
done

filtered_verbs=""
while IFS='|' read -r vid vlabel vkinds vmulti; do
  [ -n "$vid" ] || continue
  if [ "$multi" -eq 1 ] && [ "$vmulti" != "1" ]; then
    continue
  fi
  case "$vkinds" in
    *pr,issue* | *issue,pr*) ;;
    *pr*)
      [ "$has_issue" -eq 1 ] && continue
      ;;
    *issue*)
      [ "$has_pr" -eq 1 ] && continue
      ;;
  esac
  filtered_verbs+="$vid|$vlabel"$'\n'
done <<< "$verbs"

if [ -z "$filtered_verbs" ]; then
  tmux display-message "palette: no verbs applicable to selection" 2> /dev/null || true
  exit 0
fi

selection_summary="$count item"
[ "$count" -ne 1 ] && selection_summary="$count items"

_mark_selection_loading() {
  if ! declare -F gh_row_loader_start_file > /dev/null 2>&1; then
    return 0
  fi
  local cache_base="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
  mkdir -p "$cache_base" 2> /dev/null || true
  row_loader_targets_file="$(mktemp "${cache_base}/gh_row_loader_palette_XXXXXX.tsv" 2> /dev/null || true)"
  [ -n "$row_loader_targets_file" ] || return 0
  cleanup_files+=("$row_loader_targets_file")
  local i
  for i in "${!kinds[@]}"; do
    printf '%s\t%s\t%s\n' "${kinds[i]}" "${repos[i]}" "${nums[i]}" >> "$row_loader_targets_file"
  done
  row_loader_pid="$(gh_row_loader_start_file "$row_loader_targets_file" "$mode" "$scope" "$items_cmd" 2> /dev/null || true)"
}

_restore_selection_loading() {
  if declare -F gh_row_loader_stop_spinner > /dev/null 2>&1; then
    gh_row_loader_stop_spinner "$row_loader_pid" "$mode" "$scope" "$items_cmd" 2> /dev/null || true
  fi
  row_loader_pid=""
}

_refresh_after_mutation() {
  [ -n "${FZF_PORT:-}" ] || {
    _restore_selection_loading
    return 0
  }
  if [ -n "$row_loader_pid" ] && declare -F gh_row_loader_stop_spinner > /dev/null 2>&1; then
    local spinner_pid="$row_loader_pid"
    local targets_file="$row_loader_targets_file"
    (
      GH_PICKER_MODE="$mode" GH_PICKER_SCOPE="$scope" "$items_cmd" --refresh > /dev/null 2>&1 || true
      gh_row_loader_stop_spinner "$spinner_pid" "$mode" "$scope" "$items_cmd" 2> /dev/null || true
      rm -f "$targets_file" 2> /dev/null || true
    ) > /dev/null 2>&1 &
    row_loader_pid=""
    row_loader_targets_file=""
    cleanup_files=()
    return 0
  fi
  reload_cmd="GH_PICKER_MODE=$(printf %q "$mode") GH_PICKER_SCOPE=$(printf %q "$scope") $(printf %q "$items_cmd") --refresh"
  curl -s --max-time 5 -XPOST "http://127.0.0.1:${FZF_PORT}" -d "reload(${reload_cmd})+track" > /dev/null 2>&1 || true
}

chosen="$(
  printf '%s' "$filtered_verbs" \
    | fzf \
      --delimiter='|' \
      --with-nth=2 \
      --prompt="  palette ($selection_summary) > " \
      --header="enter:run · esc:cancel · mode=$mode scope=$scope" \
      --height=40% \
      --reverse \
      --no-multi \
    || true
)"

if [ -z "$chosen" ]; then
  exit 0
fi

verb_id="${chosen%%|*}"

# Read a single-line arg with bash `read` (no $EDITOR). The fzf popup is gone
# by this point, so we read from the terminal that fzf returned us to.
prompt_line() {
  local prompt="$1"
  local var
  printf '%s' "$prompt" >&2
  IFS= read -r var || return 1
  printf '%s' "$var"
}

# fzf-driven arg picker over candidate completions piped on stdin.
prompt_pick() {
  local prompt="$1"
  fzf --prompt="$prompt > " --height=40% --reverse --print-query \
    | tail -1
}

# Confirm a destructive action. Default = no.
confirm() {
  local prompt="$1"
  local reply
  reply="$(prompt_line "$prompt (y/N) ")" || return 1
  case "$reply" in
    y | Y | yes | YES) return 0 ;;
    *) return 1 ;;
  esac
}

# Collect verb-specific arguments. Sets ARG_BODY / ARG_NAME / ARG_USER /
# ARG_REASON depending on the verb. Empty for verbs that take no args.
ARG_BODY=""
ARG_NAME=""
ARG_USER=""
ARG_REASON=""

case "$verb_id" in
  close)
    if [ "$has_issue" -eq 1 ]; then
      ARG_REASON="$(python3 "$verbs_helper" close-reasons | prompt_pick 'reason (issues only, empty = none)')"
    fi
    ;;
  request-changes)
    ARG_BODY="$(prompt_line 'request-changes body: ')"
    if [ -z "$ARG_BODY" ]; then
      tmux display-message "palette: body required" 2> /dev/null || true
      exit 0
    fi
    ;;
  merge)
    repo_summary="${repos[0]}#${nums[0]}"
    if ! confirm "merge pr $repo_summary?"; then
      exit 0
    fi
    ;;
  label-add)
    primary_repo="${repos[0]}"
    ARG_NAME="$(python3 "$verbs_helper" label-completions --repo "$primary_repo" 2> /dev/null | prompt_pick "label to add (repo:$primary_repo)")"
    if [ -z "$ARG_NAME" ]; then
      tmux display-message "palette: label required" 2> /dev/null || true
      exit 0
    fi
    ;;
  label-rm)
    primary_repo="${repos[0]}"
    primary_kind="${kinds[0]}"
    primary_num="${nums[0]}"
    ARG_NAME="$(python3 "$verbs_helper" current-labels --kind "$primary_kind" --repo "$primary_repo" --num "$primary_num" 2> /dev/null | prompt_pick "label to remove (cursor item only for completion)")"
    if [ -z "$ARG_NAME" ]; then
      tmux display-message "palette: label required" 2> /dev/null || true
      exit 0
    fi
    ;;
  comment)
    ARG_BODY="$(prompt_line 'comment body: ')"
    if [ -z "$ARG_BODY" ]; then
      tmux display-message "palette: body required" 2> /dev/null || true
      exit 0
    fi
    ;;
  rr)
    primary_repo="${repos[0]}"
    ARG_USER="$(python3 "$verbs_helper" reviewer-completions --repo "$primary_repo" 2> /dev/null | prompt_pick "reviewer (repo:$primary_repo)")"
    if [ -z "$ARG_USER" ]; then
      tmux display-message "palette: reviewer required" 2> /dev/null || true
      exit 0
    fi
    ;;
esac

# Dispatch the verb once per applicable item. Single-target verbs only got
# past the verb filter when count == 1, so this loop is effectively a no-op
# for them.
_mark_selection_loading
ok=0
fail=0
declare -a errors=()
for i in "${!kinds[@]}"; do
  k="${kinds[i]}"
  r="${repos[i]}"
  n="${nums[i]}"
  declare -a cmd=(python3 "$verbs_helper" "$verb_id" --kind "$k" --repo "$r" --num "$n")
  case "$verb_id" in
    close) [ -n "$ARG_REASON" ] && cmd+=(--reason "$ARG_REASON") ;;
    request-changes) cmd+=(--body "$ARG_BODY") ;;
    label-add | label-rm) cmd+=(--name "$ARG_NAME") ;;
    comment) cmd+=(--body "$ARG_BODY") ;;
    rr) cmd+=(--user "$ARG_USER") ;;
  esac
  set +e
  err="$("${cmd[@]}" 2>&1 1> /dev/null)"
  rc=$?
  set -e
  if [ "$rc" -eq 0 ]; then
    ok=$((ok + 1))
  else
    fail=$((fail + 1))
    first_line="$(printf '%s' "$err" | head -n 1)"
    errors+=("$k $r#$n: $first_line")
  fi
done

if [ "$fail" -gt 0 ]; then
  msg="palette $verb_id: $ok ok, $fail failed"
  [ "${#errors[@]}" -gt 0 ] && msg="$msg — ${errors[0]}"
  tmux display-message "$msg" 2> /dev/null || true
else
  tmux display-message "palette $verb_id: $ok ok" 2> /dev/null || true
fi

# Refresh the outer fzf so the dashboard reflects state changes (closed/merged
# items disappear, label badges update, etc.). The selected rows keep animating
# until the background refresh replaces them.
_refresh_after_mutation
