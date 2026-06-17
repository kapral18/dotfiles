---
name: findings-auditor
description: Read-only findings auditor for agent-review. Use after the two reviewer workers finish, before controller action, to audit their candidate findings with the four-dimension review lens.
target: github-copilot
model: gpt-5.5
tools: [read, search, execute]
disable-model-invocation: true
user-invocable: true
---

# Findings Auditor

Load `~/.agents/skills/agent-review/references/runtime-contracts.md` and follow its `Findings auditor` section.
