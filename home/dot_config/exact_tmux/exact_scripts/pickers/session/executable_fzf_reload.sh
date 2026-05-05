#!/usr/bin/env bash
set -euo pipefail

cmd="${1:-}"
delay_ms="${2:-0}"

[ -n "$cmd" ] || exit 0
command -v curl > /dev/null 2>&1 || exit 0

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

action="reload($cmd)"
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
