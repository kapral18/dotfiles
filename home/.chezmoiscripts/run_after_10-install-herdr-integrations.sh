#!/usr/bin/env bash
# herdr's agent integrations edit configs the 07-merge scripts regenerate, so
# reinstall after every apply; installing a current integration changes nothing.
set -euo pipefail

command -v herdr > /dev/null 2>&1 || exit 0

status=0
for target in pi omp claude codex opencode; do
  herdr integration install "$target" > /dev/null || status=1
done
exit "$status"
