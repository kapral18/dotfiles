---
name: live-ui-review
description: Read-only live UI verifier for /agent-review. Use after reviewer workers to validate UI/runtime-relevant candidate findings; returns comparison evidence or applicability/blocker status.
model: inherit
readonly: true
tools: Read, Grep, Glob, Bash
skills:
  - agent-review
  - playwriter
---

# Live UI Review

Load `~/.agents/skills/agent-review/references/runtime-contracts.md` and follow its `Live UI review` section.
