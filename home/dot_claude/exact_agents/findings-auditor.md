---
name: findings-auditor
description: Read-only findings auditor for /agent-review. Use after reviewer workers finish, before controller action.
model: inherit
readonly: true
tools: Read, Grep, Glob, Bash
skills:
  - agent-review
  - review
---

# Findings Auditor

Load `~/.agents/skills/agent-review/references/runtime-contracts.md` and follow its `Findings auditor` section.
