#!/usr/bin/env bash
set -euo pipefail

kind="${1:-}" # "pr" or "issue"
repo="${2:-}" # best-effort, may be empty
num="${3:-}"

if [ -z "$kind" ] || [ -z "$num" ]; then
  cat
  exit 0
fi

match="$(mktemp -t sess_pin_match.XXXXXX)"
rest="$(mktemp -t sess_pin_rest.XXXXXX)"
cleanup() { rm -f "$match" "$rest" 2> /dev/null || true; }
trap cleanup EXIT

needle="|${kind}=${num}:"

awk -F $'\t' -v needle="$needle" -v mf="$match" -v rf="$rest" '
  NF < 5 { print > rf; next }
  # meta is field 4; pin session + worktree rows
  (($2 == "session" || $2 == "worktree") && index($4, needle) > 0) { print > mf; next }
  { print > rf }
'

cat "$match" "$rest"
