#!/usr/bin/env bash
# Gate git commit and push (Copilot CLI PreToolUse) to prevent rushing.
#
# Copilot CLI sends the VS Code-compatible snake_case payload (PascalCase
# event name `PreToolUse` in hooks.json) and reads back the
# `permissionDecision` contract — NOT the `decision` contract used by the
# Gemini gate. PreToolUse is fail-closed: a non-zero exit or timeout denies
# the tool call, so this script must always exit 0 and emit explicit JSON.

input=$(cat)
command=$(echo "$input" | jq -r '.tool_input.command // .toolArgs.command // empty')

if [[ "$command" =~ git[[:space:]]+.*commit ]] || [[ "$command" =~ git[[:space:]]+.*push ]]; then
  echo '{
    "permissionDecision": "deny",
    "permissionDecisionReason": "Git commit/push requires explicit user permission. Stop and ask the user before committing or pushing."
  }'
  exit 0
fi

echo '{ "permissionDecision": "allow" }'
exit 0
