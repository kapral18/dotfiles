#!/usr/bin/env bash
set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

main() {
  tmux run-shell -b "${CURRENT_DIR}/list_sessions.sh"
  tmux command-prompt -p session: "run-shell -b '${CURRENT_DIR}/switch_or_loop.sh \"%%\"'"
}
main
