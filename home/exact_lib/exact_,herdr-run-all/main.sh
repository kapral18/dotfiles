#!/usr/bin/env bash

set -euo pipefail

show_help() {
  cat << 'EOF_HELP'
Usage: ,herdr-run-all [--all] <pattern> [exclude_pattern] <command>

Run a command in herdr workspaces whose label matches a pattern.

Arguments:
    pattern         Shell pattern for workspace labels (*, ?, [])
    exclude_pattern Optional shell pattern of labels to skip
    command         Command to run

Flags:
    --all           Run in every idle pane (default: first idle pane of each workspace)
    -h, --help      Show this help message

Examples:
    ,herdr-run-all "work*" "git status"
    ,herdr-run-all "dev*" "*test*" "npm run build"
    ,herdr-run-all --all "*" "git fetch"

Notes:
    - A pane is idle when its foreground processes are all shells
      (F_HERDR_RUN_ALL_ALLOWED_SHELLS overrides "bash zsh fish sh").
    - The pane running this command goes first and is skipped when busy.
EOF_HELP
}

log_info() { echo "ℹ️  $1" >&2; }
log_error() { echo "❌ $1" >&2; }

allowed_shells="${F_HERDR_RUN_ALL_ALLOWED_SHELLS:-bash zsh fish sh}"

pane_is_idle() {
  local names name shell found
  names="$(herdr pane process-info --pane "$1" 2> /dev/null | jq -r '.result.process_info.foreground_processes[]?.name' 2> /dev/null || true)"
  [ -n "$names" ] || return 1
  while IFS= read -r name; do
    name="${name#-}"
    found=1
    for shell in $allowed_shells; do
      [ "$name" = "$shell" ] && found=0 && break
    done
    [ "$found" -eq 0 ] || return 1
  done <<< "$names"
}

main() {
  local all_panes=0
  if [ "${1:-}" = "--all" ]; then
    all_panes=1
    shift
  fi
  case "${1:-}" in -h | --help)
    show_help
    exit 0
    ;;
  esac

  local pattern exclude_pattern="" command
  case $# in
    2) pattern="$1" command="$2" ;;
    3) pattern="$1" exclude_pattern="$2" command="$3" ;;
    *)
      show_help
      exit 1
      ;;
  esac

  command -v herdr > /dev/null 2>&1 || {
    log_error "herdr is not installed or not in PATH"
    exit 1
  }
  local workspaces panes
  if ! workspaces="$(herdr workspace list 2> /dev/null | jq -r '.result.workspaces[] | [.workspace_id, .label] | join("\t")')"; then
    log_error "No herdr server is running"
    exit 1
  fi
  panes="$(herdr pane list | jq -r '.result.panes[] | [.workspace_id, .pane_id] | join("\t")')"

  local matched=0 ok=0 failed=0 skipped=0 ws_id label pane_ws pane_id
  local current="${HERDR_PANE_ID:-}"
  while IFS=$'\t' read -r ws_id label; do
    [ -n "$ws_id" ] || continue
    # shellcheck disable=SC2053
    [[ $label == $pattern ]] || continue
    # shellcheck disable=SC2053
    [[ -n "$exclude_pattern" && $label == $exclude_pattern ]] && continue
    matched=$((matched + 1))

    local queue=()
    while IFS=$'\t' read -r pane_ws pane_id; do
      [ "$pane_ws" = "$ws_id" ] || continue
      if [ "$pane_id" = "$current" ]; then
        queue=("$pane_id" "${queue[@]+"${queue[@]}"}")
      else
        queue+=("$pane_id")
      fi
    done <<< "$panes"

    local sent=0
    for pane_id in "${queue[@]+"${queue[@]}"}"; do
      if ! pane_is_idle "$pane_id"; then
        skipped=$((skipped + 1))
        continue
      fi
      if herdr pane run "$pane_id" "$command" > /dev/null 2>&1; then
        ok=$((ok + 1))
      else
        log_error "Failed to send command to pane '$pane_id' ($label)"
        failed=$((failed + 1))
      fi
      sent=1
      [ "$all_panes" -eq 1 ] || break
    done
    [ "$sent" -eq 1 ] || log_info "No idle pane in workspace '$label' (skipped)"
  done <<< "$workspaces"

  if [ "$matched" -eq 0 ]; then
    log_error "No workspaces match pattern '$pattern'${exclude_pattern:+ (excluding '$exclude_pattern')}"
    exit 1
  fi
  log_info "Workspaces matched: $matched"
  log_info "Panes: $ok successful, $failed failed, $skipped skipped"
  [ "$failed" -eq 0 ]
}

main "$@"
