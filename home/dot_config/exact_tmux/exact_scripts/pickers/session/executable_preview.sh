#!/usr/bin/env bash
set -euo pipefail

# Kill child processes (git, tmux, awk) when fzf terminates this preview.
trap 'pkill -P $$ 2>/dev/null || true' INT TERM HUP

kind=""
path=""
meta=""
target=""

args=()
for a in "$@"; do
  case "$a" in
    --kind=*) kind="${a#--kind=}" ;;
    --path=*) path="${a#--path=}" ;;
    --meta=*) meta="${a#--meta=}" ;;
    --target=*) target="${a#--target=}" ;;
    *) args+=("$a") ;;
  esac
done
set -- "${args[@]+"${args[@]}"}"

if [ -z "$kind" ] && [ -z "$path" ]; then
  if [ -f "${1:-}" ]; then
    line="$(head -n 1 "$1" 2> /dev/null || true)"
  else
    line="${1:-}"
  fi
  if [ -n "$line" ]; then
    IFS=$'\t' read -r _disp kind path meta target _rest <<< "$line"
  fi
fi

[ -n "$kind" ] && [ -n "$path" ] || exit 0

C_DIM=$'\033[2m'
C_BOLD=$'\033[1m'
C_BLUE=$'\033[38;5;111m'
C_GREEN=$'\033[38;5;150m'
C_YELLOW=$'\033[38;5;214m'
C_CYAN=$'\033[38;5;81m'
C_R=$'\033[0m'

C_PURPLE=$'\033[38;5;141m'
C_RED=$'\033[38;5;196m'

gh_info_from_meta() {
  local m="$1"
  [ -n "$m" ] || return 0
  local IFS='|'
  local part num state review ci url
  local _gh_cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
  for part in $m; do
    case "$part" in
      pr=*)
        IFS=':' read -r num state review ci url <<< "${part#pr=}"
        if [ -n "$num" ]; then
          local sc="$C_GREEN"
          local icon="open"
          case "${state^^}" in
            MERGED)
              sc="$C_PURPLE"
              icon="merged"
              ;;
            CLOSED)
              sc="$C_RED"
              icon="closed"
              ;;
          esac
          local review_label=""
          case "${review^^}" in
            APPROVED) review_label="${C_GREEN}approved${C_R}" ;;
            CHANGES_REQUESTED) review_label="${C_RED}changes requested${C_R}" ;;
            REVIEW_REQUIRED) review_label="${C_YELLOW}review pending${C_R}" ;;
          esac
          printf '%s  %sPR #%s%s %s(%s)%s' "${C_DIM}gh${C_R}" "$sc" "$num" "$C_R" "$C_DIM" "$icon" "$C_R"
          [ -n "$review_label" ] && printf '  %s' "$review_label"
          if [ -n "$url" ]; then
            printf '  %s%s%s' "$C_DIM" "$url" "$C_R"
            local repo=""
            case "$url" in
              https://github.com/*/*)
                local url_path="${url#https://github.com/}"
                local owner="${url_path%%/*}"
                local rest="${url_path#*/}"
                local rname="${rest%%/*}"
                [ -n "$owner" ] && [ -n "$rname" ] && repo="${owner}/${rname}"
                ;;
            esac
            if [ -n "$repo" ]; then
              local title=""
              title="$(awk -F $'\t' -v k="pr" -v r="$repo" -v n="$num" '$2==k && $3==r && $4==n {print $1; exit}' "$_gh_cache_dir/gh_picker_work.tsv" "$_gh_cache_dir/gh_picker_home.tsv" 2> /dev/null || true)"
              [ -n "$title" ] && printf '\n%s  %s' "${C_DIM}title${C_R}" "$title"
            fi
          fi
          printf '\n'
        fi
        ;;
      issue=*)
        IFS=':' read -r num state url <<< "${part#issue=}"
        if [ -n "$num" ]; then
          local ic="$C_GREEN"
          local ilabel="open"
          case "${state^^}" in
            CLOSED | COMPLETED | NOT_PLANNED)
              ic="$C_PURPLE"
              ilabel="closed"
              ;;
            MERGED)
              ic="$C_PURPLE"
              ilabel="merged"
              ;;
          esac
          printf '%s  %sIssue #%s%s %s(%s)%s' "${C_DIM}gh${C_R}" "$ic" "$num" "$C_R" "$C_DIM" "$ilabel" "$C_R"
          if [ -n "$url" ]; then
            printf '  %s%s%s' "$C_DIM" "$url" "$C_R"
            local repo=""
            case "$url" in
              https://github.com/*/*)
                local url_path="${url#https://github.com/}"
                local owner="${url_path%%/*}"
                local rest="${url_path#*/}"
                local rname="${rest%%/*}"
                [ -n "$owner" ] && [ -n "$rname" ] && repo="${owner}/${rname}"
                ;;
            esac
            if [ -n "$repo" ]; then
              local title=""
              title="$(awk -F $'\t' -v k="issue" -v r="$repo" -v n="$num" '$2==k && $3==r && $4==n {print $1; exit}' "$_gh_cache_dir/gh_picker_work.tsv" "$_gh_cache_dir/gh_picker_home.tsv" 2> /dev/null || true)"
              [ -n "$title" ] && printf '\n%s  %s' "${C_DIM}title${C_R}" "$title"
            fi
          fi
          printf '\n'
        fi
        ;;
    esac
  done
}

git_summary() {
  local dir="$1"
  [ -d "$dir" ] || return 0
  [ -e "$dir/.git" ] || return 0

  if ! git -C "$dir" rev-parse --git-dir > /dev/null 2>&1; then
    printf '%s  %s%s%s\n' "${C_DIM}git${C_R}" "$C_YELLOW" "stale worktree (gitdir missing)" "$C_R"
    printf '\n%s\n' "${C_BOLD}${C_CYAN}contents${C_R}"
    ls -1 "$dir" 2> /dev/null | head -20 || true
    return 0
  fi

  local branch
  branch="$(git -C "$dir" symbolic-ref --quiet --short HEAD 2> /dev/null || git -C "$dir" rev-parse --short HEAD 2> /dev/null || true)"
  if [ -n "$branch" ]; then
    printf '%s  %s%s%s\n' "${C_DIM}branch${C_R}" "$C_GREEN" "$branch" "$C_R"
  fi

  # Combine ahead/behind into one rev-list call.
  local lr
  lr="$(git -C "$dir" rev-list --left-right --count '@{upstream}...HEAD' 2> /dev/null || true)"
  if [ -n "$lr" ]; then
    local behind ahead
    read -r behind ahead <<< "$lr"
    if [ "${ahead:-0}" != "0" ] || [ "${behind:-0}" != "0" ]; then
      printf '%s  ' "${C_DIM}sync${C_R}"
      [ "${ahead:-0}" != "0" ] && printf '%s↑%s%s ' "$C_YELLOW" "$ahead" "$C_R"
      [ "${behind:-0}" != "0" ] && printf '%s↓%s%s ' "$C_BLUE" "$behind" "$C_R"
      printf '\n'
    fi
  fi

  local log_lines
  log_lines="$(git -C "$dir" log --oneline --no-decorate -6 2> /dev/null || true)"
  if [ -n "$log_lines" ]; then
    printf '\n%s\n' "${C_BOLD}${C_CYAN}recent commits${C_R}"
    printf '%s\n' "$log_lines"
  fi
}

pane_capture() {
  local sess="$1"
  [ -n "$sess" ] || return 0

  # Single tmux call for session metadata: command, path, window count.
  local sess_info
  sess_info="$(tmux display-message -t "$sess" -p '#{pane_current_command}	#{session_path}	#{session_windows}' 2> /dev/null || true)"
  if [ -n "$sess_info" ]; then
    local active_cmd sess_path win_count
    IFS=$'\t' read -r active_cmd sess_path win_count <<< "$sess_info"

    if [ -n "$active_cmd" ]; then
      printf '%s  %s%s%s\n' "${C_DIM}running${C_R}" "$C_YELLOW" "$active_cmd" "$C_R"
    fi

    if [ -n "$sess_path" ]; then
      local tpath="$sess_path"
      case "$sess_path" in
        "$HOME") tpath="~" ;;
        "$HOME"/*) tpath="~/${sess_path#"$HOME"/}" ;;
      esac
      printf '%s  %s%s%s\n' "${C_DIM}path${C_R}" "$C_BLUE" "$tpath" "$C_R"
    fi

    case "$win_count" in
      '' | 0 | 1) ;;
      *) printf '%s  %s windows\n' "${C_DIM}layout${C_R}" "$win_count" ;;
    esac
  fi

  local pane_text
  pane_text="$(tmux capture-pane -t "$sess" -p 2> /dev/null | awk 'NF{p=1} p' || true)"
  if [ -n "$pane_text" ]; then
    printf '\n%s\n' "${C_BOLD}${C_CYAN}pane content${C_R}"
    printf '%s\n' "$pane_text" | tail -20
  else
    printf '\n%s\n' "${C_DIM}(empty pane)${C_R}"
  fi
}

dir_preview() {
  local dir="$1"
  [ -d "$dir" ] || {
    printf 'directory not found: %s\n' "$dir"
    return 0
  }

  local tpath="$dir"
  case "$dir" in
    "$HOME") tpath="~" ;;
    "$HOME"/*) tpath="~/${dir#"$HOME"/}" ;;
  esac
  printf '%s  %s%s%s\n' "${C_DIM}path${C_R}" "$C_BLUE" "$tpath" "$C_R"

  if [ -e "$dir/.git" ]; then
    git_summary "$dir"
  else
    printf '\n%s\n' "${C_BOLD}${C_CYAN}contents${C_R}"
    ls -1 "$dir" 2> /dev/null | head -20 || true
  fi
}

ralph_info_from_meta() {
  local m="$1"
  local sess="$2"
  local status=""
  local IFS='|'
  for part in $m; do
    case "$part" in
      ralph=*) status="${part#ralph=}" ;;
    esac
  done
  [ -z "$status" ] && return 0
  local sc="$C_BLUE"
  case "$status" in
    passed | completed) sc="$C_GREEN" ;;
    needs_verification) sc="$C_YELLOW" ;;
    failed) sc="$C_RED" ;;
    killed) sc="${C_DIM}" ;;
  esac
  printf '%s  %s%s%s\n' "${C_DIM}ralph${C_R}" "$sc" "$status" "$C_R"
  if [ -n "$sess" ] && command -v ,ralph > /dev/null 2>&1; then
    local match
    match="$(,ralph runs --json --session "$sess" --limit 5 2> /dev/null || true)"
    if [ -n "$match" ] && [ "$match" != "[]" ]; then
      printf '%s  %s\n' "${C_DIM}runs${C_R}" "$(printf '%s' "$match" | python3 -c "
import json, sys
rows = json.load(sys.stdin)
for r in rows[:3]:
    print(f\"  {r.get('name') or r.get('short_id')}  {r.get('status')}/{r.get('validation_status') or '-'}  {(r.get('goal') or '')[:60]}\")
" 2> /dev/null)"
    fi
  fi
}

case "$kind" in
  session)
    gh_info_from_meta "$meta"
    ralph_info_from_meta "$meta" "$target"
    if [ -n "$target" ]; then
      pane_capture "$target"
    elif [ -n "$path" ] && [ -d "$path" ]; then
      dir_preview "$path"
    fi
    ;;
  worktree)
    gh_info_from_meta "$meta"
    ralph_info_from_meta "$meta" ""
    if [ -n "$path" ] && [ -d "$path" ]; then
      dir_preview "$path"
    fi
    ;;
  dir)
    if [ -n "$path" ] && [ -d "$path" ]; then
      dir_preview "$path"
    fi
    ;;
  *)
    printf '%s\n' "$line"
    ;;
esac
