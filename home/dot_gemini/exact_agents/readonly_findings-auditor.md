---
name: findings-auditor
description: Read-only findings auditor for /agent-review. Use after Gemini reviewer workers finish, before controller action.
kind: local
tools:
  - read_file
  - list_directory
  - glob
  - grep_search
  - run_shell_command
model: gemini-pro-latest
temperature: 0.1
max_turns: 20
---

# Findings Auditor

Load `~/.agents/skills/agent-review/references/runtime-contracts.md` and follow its `Findings auditor` section.
