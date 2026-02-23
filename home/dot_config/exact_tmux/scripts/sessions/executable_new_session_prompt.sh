#!/usr/bin/env bash
set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

main() {
  tmux command-prompt -p "new session name:" "run-shell -b '${CURRENT_DIR}/new_session.sh \"%%\"'"
}
main
