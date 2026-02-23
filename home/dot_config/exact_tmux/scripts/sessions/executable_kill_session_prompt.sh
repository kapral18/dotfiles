#!/usr/bin/env bash
set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CURRENT_SESSION_NAME="${1:-}"
CURRENT_SESSION_ID="${2:-}"

main() {
  tmux confirm -p "kill-session ${CURRENT_SESSION_NAME}? (y/n)" "run-shell -b '${CURRENT_DIR}/kill_session.sh \"${CURRENT_SESSION_ID}\"'"
}
main
