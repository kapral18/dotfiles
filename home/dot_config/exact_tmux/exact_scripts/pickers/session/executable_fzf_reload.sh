#!/usr/bin/env bash
set -euo pipefail

cmd="${1:-}"
delay_ms="${2:-0}"

[ -n "$cmd" ] || exit 0
command -v curl > /dev/null 2>&1 || exit 0

if [ -n "${PICK_SESSION_SORT_SOURCE_FILE:-}" ]; then
  cmd="{ $cmd | tee \"\${PICK_SESSION_SORT_SOURCE_FILE}.new.\$\$\"; mv -f \"\${PICK_SESSION_SORT_SOURCE_FILE}.new.\$\$\" \"\$PICK_SESSION_SORT_SOURCE_FILE\"; }"
fi

case "$delay_ms" in
  '' | *[!0-9]*) delay_ms=0 ;;
esac

if [ "$delay_ms" -gt 0 ]; then
  if [ "$delay_ms" -ge 1000 ]; then
    sleep "$((delay_ms / 1000)).$((delay_ms % 1000))"
  else
    sleep "0.$(printf '%03d' "$delay_ms")"
  fi
fi

# `+track` preserves the highlighted row's identity across the reload so a
# background-triggered reload (live_refresh tick, ordering pass, deferred
# dir-row reload) doesn't scroll the user back to the top mid-interaction.
# Matches the explicit ctrl-r/alt-r bindings in pick_session.sh.
action="reload($cmd)+track"
if [ -n "${FZF_SOCK:-}" ]; then
  if [ -n "${FZF_API_KEY:-}" ]; then
    curl --silent --show-error --fail --unix-socket "$FZF_SOCK" -H "x-api-key: ${FZF_API_KEY}" -X POST http://localhost --data "$action" > /dev/null 2>&1 || true
  else
    curl --silent --show-error --fail --unix-socket "$FZF_SOCK" -X POST http://localhost --data "$action" > /dev/null 2>&1 || true
  fi
  exit 0
fi

if [ -n "${FZF_PORT:-}" ]; then
  if [ -n "${FZF_API_KEY:-}" ]; then
    curl --silent --show-error --fail -H "x-api-key: ${FZF_API_KEY}" -X POST "http://127.0.0.1:${FZF_PORT}" --data "$action" > /dev/null 2>&1 || true
  else
    curl --silent --show-error --fail -X POST "http://127.0.0.1:${FZF_PORT}" --data "$action" > /dev/null 2>&1 || true
  fi
fi
