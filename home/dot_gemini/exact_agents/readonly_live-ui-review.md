---
name: live-ui-review
description: Manual-only live UI/runtime review probe for /agent-review. Use only when explicitly requested; never auto-trigger.
kind: local
tools:
  - read_file
  - list_directory
  - glob
  - grep_search
  - run_shell_command
model: gemini-pro-latest
temperature: 0.1
max_turns: 30
---

# Live UI Review

Load `~/.agents/skills/agent-review/references/runtime-contracts.md` and follow its `Live UI review` section.
