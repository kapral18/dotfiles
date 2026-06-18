---
name: live-ui-review
description: Read-only live UI verifier for /agent-review. Use after reviewer workers to validate UI/runtime-relevant candidate findings; returns comparison evidence or applicability/blocker status.
target: github-copilot
model: gpt-5.5
tools: [read, search, execute, web]
disable-model-invocation: true
user-invocable: true
---

# Live UI Review

Load `~/.agents/skills/agent-review/references/runtime-contracts.md` and follow its `Live UI review` section.
