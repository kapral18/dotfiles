---
name: live-ui-review
description: Manual-only live UI/runtime review probe. Use only when the user explicitly asks to compare a live PR UI/runtime instance against main/base before review aggregation; never auto-trigger from /agent-review.
target: github-copilot
model: gpt-5.5
tools: [read, search, execute, web]
disable-model-invocation: true
user-invocable: true
---

# Live UI Review

Load `~/.agents/skills/agent-review/references/runtime-contracts.md` and follow its `Live UI review` section.
