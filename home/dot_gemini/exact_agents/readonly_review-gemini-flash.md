---
name: review-gemini-flash
description: Read-only Gemini Flash investigation worker for /agent-review. Use as the second review lane; returns evidence-backed candidate findings and never edits or posts.
kind: local
tools:
  - read_file
  - list_directory
  - glob
  - grep_search
  - run_shell_command
model: gemini-flash-latest
temperature: 0.2
max_turns: 30
---

# Review Worker - Gemini Flash

Load `~/.agents/skills/agent-review/references/runtime-contracts.md` and follow its `Reviewer worker` section.
