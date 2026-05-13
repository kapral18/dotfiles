#!/bin/bash
# Gate PR review comments to prevent line anchor hallucinations.

input=$(cat)
command=$(echo "$input" | jq -r '.command // empty')

is_gemini_cli=false
if [[ -z "$command" ]]; then
  command=$(echo "$input" | jq -r '.tool_input.command // empty')
  is_gemini_cli=true
fi

# 1. Check if the command includes a payload with line/position anchors
has_anchor=false
if [[ "$command" =~ "line=" ]] || [[ "$command" =~ "position=" ]] || [[ "$command" =~ "start_line=" ]]; then
  has_anchor=true
elif [[ "$command" =~ "--input " ]] || [[ "$command" =~ "-X POST" ]]; then
  has_anchor=true
fi

if [[ "$has_anchor" == "false" ]]; then
  if [[ "$is_gemini_cli" == "true" ]]; then
    echo '{ "decision": "allow" }'
  else
    echo '{ "permission": "allow" }'
  fi
  exit 0
fi

# 3. Gate it with an explicit user prompt
if [[ "$is_gemini_cli" == "true" ]]; then
  echo '{
    "decision": "deny",
    "reason": "⚠️ GEMINI ANCHOR WARNING: Gemini models frequently hallucinate PR review line anchors based on full-file context instead of the diff. You MUST fetch `gh pr diff` and recalculate the line numbers to ensure they are inside the hunks before proceeding."
  }'
else
  echo '{
    "permission": "ask",
    "user_message": "⚠️ GEMINI ANCHOR WARNING: Gemini models frequently hallucinate PR review line anchors based on full-file context instead of the diff. Please check the command payload. Do the line numbers exist inside the PR diff hunks? If no, click Deny.",
    "agent_message": "The user is being asked to manually verify your line anchors. If they deny this request, you MUST fetch `gh pr diff` and recalculate the line numbers to ensure they are inside the hunks."
  }'
fi
exit 0
