#!/usr/bin/env bash
set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CURRENT_SESSION_NAME="${1:-}"
CURRENT_SESSION_ID="${2:-}"

main() {
  # Session IDs look like `$120`. If we pass that through `run-shell` without
  # escaping, `/bin/sh -c` will treat `$120` as `$1` + `20` and the kill will
  # silently target the wrong (or empty) id. Escape `$` so the argument reaches
  # the script literally.
  local safe_id
  safe_id="${CURRENT_SESSION_ID//\\/\\\\}"
  safe_id="${safe_id//\$/\\$}"
  tmux confirm -p "kill-session ${CURRENT_SESSION_NAME}? (y/n)" "run-shell -b '${CURRENT_DIR}/kill_session.sh \"${safe_id}\"'"
}
main
