---
name: agent-review
description: Orchestrates the investigation-only multi-agent review flow. Use when the user invokes /agent-review or asks for the agentic review orchestration.
target: github-copilot
model: gpt-5.5
tools: [read, search, execute, edit, agent]
disable-model-invocation: false
user-invocable: true
---

# Agent Review

Load and follow `~/.agents/skills/agent-review/SKILL.md`.
