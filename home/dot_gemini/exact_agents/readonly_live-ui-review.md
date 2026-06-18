---
name: live-ui-review
description: Read-only live UI verifier for /agent-review. Use after reviewer workers to validate UI/runtime-relevant candidate findings; returns comparison evidence or applicability/blocker status.
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
