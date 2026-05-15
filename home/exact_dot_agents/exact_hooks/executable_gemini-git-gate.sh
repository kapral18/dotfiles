#!/usr/bin/env bash
# Gate git commit and push to prevent rushing.

input=$(cat)
command=$(echo "$input" | jq -r '.command // empty')

is_gemini_cli=false
if [[ -z "$command" ]]; then
  command=$(echo "$input" | jq -r '.tool_input.command // empty')
  is_gemini_cli=true
fi

# 1. Check if the command includes a git commit or push
if [[ "$command" =~ git[[:space:]]+.*commit ]] || [[ "$command" =~ git[[:space:]]+.*push ]]; then
  if [[ "$is_gemini_cli" == "true" ]]; then
    echo '{
      "decision": "deny",
      "reason": "⚠️ GEMINI GIT WARNING: Gemini models frequently rush to commit and push without explicit permission. Stop and ask the user what to do next."
    }'
  else
    echo '{
      "permission": "ask",
      "user_message": "⚠️ GEMINI GIT WARNING: Gemini models frequently rush to commit and push without explicit permission. Did you explicitly ask the agent to commit or push? If no, click Deny.",
      "agent_message": "The user denied your git commit/push because you did not ask for explicit permission first. Stop and ask the user what to do next."
    }'
  fi
  exit 0
fi

if [[ "$is_gemini_cli" == "true" ]]; then
  echo '{ "decision": "allow" }'
else
  echo '{ "permission": "allow" }'
fi
exit 0
