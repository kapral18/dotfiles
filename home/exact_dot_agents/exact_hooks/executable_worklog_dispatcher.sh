#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
recorder="$script_dir/worklog_recorder.py"

if ! command -v python3 > /dev/null 2>&1; then
  printf '%s\n' "[agent-worklog] python3 not found; worklog event was not dispatched" >&2
  exit 1
fi
if [ ! -r "$recorder" ]; then
  printf '%s\n' "[agent-worklog] recorder not found: $recorder" >&2
  exit 1
fi

payload=$(cat)
if [ -z "$payload" ]; then
  printf '%s\n' "[agent-worklog] empty hook payload; worklog event was not dispatched" >&2
  exit 1
fi

(printf '%s' "$payload" | AGENT_WORKLOG_DISPATCHED=1 python3 "$recorder") > /dev/null 2>&1 &
