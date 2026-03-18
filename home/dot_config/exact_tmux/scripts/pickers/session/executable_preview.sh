#!/usr/bin/env bash
set -euo pipefail

# Debounce: if the user is scrolling rapidly, fzf will kill this process
# before the sleep finishes, avoiding heavy tmux/git commands.
sleep 0.1

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
    kind="$(printf '%s' "$line" | awk -F $'\t' '{print $2}')"
    path="$(printf '%s' "$line" | awk -F $'\t' '{print $3}')"
    meta="$(printf '%s' "$line" | awk -F $'\t' '{print $4}')"
    target="$(printf '%s' "$line" | awk -F $'\t' '{print $5}')"
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

header() {
  printf '%s%s%s\n' "$C_BOLD$C_CYAN" "$1" "$C_R"
}

gh_info_from_meta() {
  local m="$1"
  [ -n "$m" ] || return 0
  local IFS='|'
  local part num state review ci url
  for part in $m; do
    case "$part" in
      pr=*)
        IFS=':' read -r num state review ci url <<< "${part#pr=}"
        if [ -n "$num" ]; then
          local sc="$C_GREEN"
          local icon="open"
          local state_upper
          state_upper="$(printf '%s' "$state" | tr '[:lower:]' '[:upper:]')"
          case "$state_upper" in
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
          local review_upper
          review_upper="$(printf '%s' "$review" | tr '[:lower:]' '[:upper:]')"
          case "$review_upper" in
            APPROVED) review_label="${C_GREEN}approved${C_R}" ;;
            CHANGES_REQUESTED) review_label="${C_RED}changes requested${C_R}" ;;
            REVIEW_REQUIRED) review_label="${C_YELLOW}review pending${C_R}" ;;
          esac
          printf '%s  %sPR #%s%s %s(%s)%s' "$(dim 'gh')" "$sc" "$num" "$C_R" "$C_DIM" "$icon" "$C_R"
          if [ -n "$review_label" ]; then
            printf '  %s' "$review_label"
          fi
          if [ -n "$url" ]; then
            printf '  %s%s%s' "$C_DIM" "$url" "$C_R"

            local repo=""
            case "$url" in
              https://github.com/*/*)
                local url_path="${url#https://github.com/}"
                local owner="${url_path%%/*}"
                local rest="${url_path#*/}"
                local name="${rest%%/*}"
                if [ -n "$owner" ] && [ -n "$name" ]; then
                  repo="${owner}/${name}"
                fi
                ;;
            esac
            if [ -n "$repo" ]; then
              local title=""
              title="$(awk -F $'\t' -v k="pr" -v r="$repo" -v n="$num" '$2==k && $3==r && $4==n {print $1; exit}' "${XDG_CACHE_HOME:-$HOME/.cache}/tmux/gh_picker_work.tsv" "${XDG_CACHE_HOME:-$HOME/.cache}/tmux/gh_picker_home.tsv" 2> /dev/null || true)"
              if [ -n "$title" ]; then
                printf '\n%s  %s' "$(dim 'title')" "$title"
              fi
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
          local state_upper
          state_upper="$(printf '%s' "$state" | tr '[:lower:]' '[:upper:]')"
          case "$state_upper" in
            CLOSED | COMPLETED | NOT_PLANNED)
              ic="$C_PURPLE"
              ilabel="closed"
              ;;
            MERGED)
              ic="$C_PURPLE"
              ilabel="merged"
              ;;
          esac
          printf '%s  %sIssue #%s%s %s(%s)%s' "$(dim 'gh')" "$ic" "$num" "$C_R" "$C_DIM" "$ilabel" "$C_R"
          if [ -n "$url" ]; then
            printf '  %s%s%s' "$C_DIM" "$url" "$C_R"

            local repo=""
            case "$url" in
              https://github.com/*/*)
                local url_path="${url#https://github.com/}"
                local owner="${url_path%%/*}"
                local rest="${url_path#*/}"
                local name="${rest%%/*}"
                if [ -n "$owner" ] && [ -n "$name" ]; then
                  repo="${owner}/${name}"
                fi
                ;;
            esac
            if [ -n "$repo" ]; then
              local title=""
              title="$(awk -F $'\t' -v k="issue" -v r="$repo" -v n="$num" '$2==k && $3==r && $4==n {print $1; exit}' "${XDG_CACHE_HOME:-$HOME/.cache}/tmux/gh_picker_work.tsv" "${XDG_CACHE_HOME:-$HOME/.cache}/tmux/gh_picker_home.tsv" 2> /dev/null || true)"
              if [ -n "$title" ]; then
                printf '\n%s  %s' "$(dim 'title')" "$title"
              fi
            fi
          fi
          printf '\n'
        fi
        ;;
    esac
  done
}

dim() {
  printf '%s%s%s' "$C_DIM" "$1" "$C_R"
}

git_summary() {
  local dir="$1"
  [ -d "$dir" ] || return 0
  [ -e "$dir/.git" ] || return 0

  if ! timeout 0.2 git -C "$dir" rev-parse --git-dir > /dev/null 2>&1; then
    printf '%s  %s%s%s\n' "$(dim 'git')" "$C_YELLOW" "stale worktree (gitdir missing)" "$C_R"
    printf '\n%s\n' "$(header 'contents')"
    timeout 0.2 ls -1 --color=always "$dir" 2> /dev/null | head -20 || timeout 0.2 ls -1 "$dir" 2> /dev/null | head -20 || true
    return 0
  fi

  local branch status_lines log_lines

  branch="$(timeout 0.2 git -C "$dir" symbolic-ref --quiet --short HEAD 2> /dev/null || timeout 0.2 git -C "$dir" rev-parse --short HEAD 2> /dev/null || true)"
  if [ -n "$branch" ]; then
    printf '%s  %s%s%s\n' "$(dim 'branch')" "$C_GREEN" "$branch" "$C_R"
  fi

  local ahead behind
  ahead="$(timeout 0.2 git -C "$dir" rev-list --count '@{upstream}..HEAD' 2> /dev/null || true)"
  behind="$(timeout 0.2 git -C "$dir" rev-list --count 'HEAD..@{upstream}' 2> /dev/null || true)"
  if [ "${ahead:-0}" != "0" ] || [ "${behind:-0}" != "0" ]; then
    printf '%s  ' "$(dim 'sync')"
    [ "${ahead:-0}" != "0" ] && printf '%s↑%s%s ' "$C_YELLOW" "$ahead" "$C_R"
    [ "${behind:-0}" != "0" ] && printf '%s↓%s%s ' "$C_BLUE" "$behind" "$C_R"
    printf '\n'
  fi

  local all_status
  all_status="$(timeout 0.5 git -C "$dir" status --porcelain -uno 2> /dev/null || true)"
  if [ -n "$all_status" ]; then
    local total
    total="$(printf '%s\n' "$all_status" | grep -c '^' || true)"
    status_lines="$(printf '%s\n' "$all_status" | head -8)"
    printf '\n%s\n' "$(header "changes ($total)")"
    printf '%s\n' "$status_lines"
    [ "$total" -gt 8 ] 2> /dev/null && printf '%s\n' "$(dim "  … and $((total - 8)) more")"
  fi

  log_lines="$(timeout 0.2 git -C "$dir" log --oneline --no-decorate -6 2> /dev/null || true)"
  if [ -n "$log_lines" ]; then
    printf '\n%s\n' "$(header 'recent commits')"
    printf '%s\n' "$log_lines"
  fi
}

pane_capture() {
  local sess="$1"
  [ -n "$sess" ] || return 0

  local pane_info active_cmd
  pane_info="$(timeout 0.2 tmux list-panes -t "$sess" -F '#{pane_index} #{pane_current_command} #{pane_pid}' 2> /dev/null | head -1 || true)"
  if [ -n "$pane_info" ]; then
    active_cmd="$(printf '%s' "$pane_info" | awk '{print $2}')"
    if [ -n "$active_cmd" ]; then
      printf '%s  %s%s%s\n' "$(dim 'running')" "$C_YELLOW" "$active_cmd" "$C_R"
    fi
  fi

  local sess_path
  sess_path="$(timeout 0.2 tmux display-message -t "$sess" -p '#{session_path}' 2> /dev/null || true)"
  if [ -n "$sess_path" ]; then
    local tpath="$sess_path"
    case "$sess_path" in
      "$HOME") tpath="~" ;;
      "$HOME"/*) tpath="~/${sess_path#"$HOME"/}" ;;
    esac
    printf '%s  %s%s%s\n' "$(dim 'path')" "$C_BLUE" "$tpath" "$C_R"
  fi

  local windows
  windows="$(timeout 0.2 tmux list-windows -t "$sess" -F '#{window_index}:#{window_name} #{window_active}' 2> /dev/null || true)"
  local win_count
  win_count="$(printf '%s\n' "$windows" | grep -c . || true)"
  if [ "${win_count:-0}" -gt 1 ]; then
    printf '%s  %s windows\n' "$(dim 'layout')" "$win_count"
  fi

  local pane_text
  pane_text="$(timeout 0.2 tmux capture-pane -t "$sess" -p 2> /dev/null | awk 'NF{p=1} p' || true)"
  if [ -n "$pane_text" ]; then
    printf '\n%s\n' "$(header 'pane content')"
    printf '%s\n' "$pane_text" | tail -20
  else
    printf '\n%s\n' "$(dim '(empty pane)')"
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
  printf '%s  %s%s%s\n' "$(dim 'path')" "$C_BLUE" "$tpath" "$C_R"

  if [ -e "$dir/.git" ]; then
    git_summary "$dir"
  else
    printf '\n%s\n' "$(header 'contents')"
    timeout 0.2 ls -1 --color=always "$dir" 2> /dev/null | head -20 || timeout 0.2 ls -1 "$dir" 2> /dev/null | head -20 || true
  fi
}

case "$kind" in
  session)
    gh_info_from_meta "$meta"
    if [ -n "$target" ]; then
      pane_capture "$target"
    elif [ -n "$path" ] && [ -d "$path" ]; then
      dir_preview "$path"
    fi
    ;;
  worktree)
    gh_info_from_meta "$meta"
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
