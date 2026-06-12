#!/usr/bin/env bash
# Gate PR review comments (Copilot CLI PreToolUse) to prevent line-anchor
# hallucinations.
#
# Copilot CLI sends the VS Code-compatible snake_case payload and reads back
# the `permissionDecision` contract. PreToolUse is fail-closed, so this script
# must always exit 0 and emit explicit JSON.

input=$(cat)
command=$(echo "$input" | jq -r '.tool_input.command // .toolArgs.command // empty')

has_anchor=false
if [[ "$command" =~ "line=" ]] || [[ "$command" =~ "position=" ]] || [[ "$command" =~ "start_line=" ]]; then
  has_anchor=true
elif [[ "$command" =~ "--input " ]] || [[ "$command" =~ "-X POST" ]]; then
  has_anchor=true
fi

if [[ "$has_anchor" == "false" ]]; then
  echo '{ "permissionDecision": "allow" }'
  exit 0
fi

echo '{
  "permissionDecision": "deny",
  "permissionDecisionReason": "This command posts PR review line anchors. Fetch `gh pr diff` and recalculate the line numbers to confirm they fall inside the diff hunks before proceeding."
}'
exit 0
