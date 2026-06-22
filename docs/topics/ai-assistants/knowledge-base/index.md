---
title: Agent Memory
---

# Agent Memory

Two memory systems serve different jobs: short-lived topic context keeps the current session coherent, while the durable KB carries reusable lessons across agents and runs.

| Layer              | Lifetime                | Storage                   | Main controls             | Details                                     |
| ------------------ | ----------------------- | ------------------------- | ------------------------- | ------------------------------------------- |
| Hook memory        | current workspace/topic | `/tmp/specs/...`          | `,agent-memory`           | [Hook memory](hook-memory.md)               |
| Durable KB         | cross-session           | `~/.local/share/ai-kb/`   | `,ai-kb`                  | [AI knowledge base](ai-kb.md)               |
| Cross-agent recall | runtime-specific        | shared KB + hooks/plugins | skill-driven search/write | [Cross-agent memory](cross-agent-memory.md) |

## Read path

1. Start with [Hook memory](hook-memory.md) to see how `/tmp/specs` rehydrates active work.
2. Continue to [AI knowledge base](ai-kb.md) for capsule schema, search, embeddings, and Ralph learning.
3. Finish with [Cross-agent memory](cross-agent-memory.md) for Cursor, Pi, Claude, Gemini, OpenCode, Codex, Copilot, and Ralph injection rules.

## Operating boundary

| System                      | Use for                                   | Do not use for          |
| --------------------------- | ----------------------------------------- | ----------------------- |
| `,agent-memory`             | session topic, worklog, evidence ledger   | durable lessons         |
| `,ai-kb`                    | verified reusable facts, gotchas, recipes | transient scratch notes |
| SCSI / semantic-code-search | repository code search                    | agent memory            |

## Related

- [Ralph orchestrator](../ralph/index.md) — primary mechanical producer/consumer of KB capsules
- [The Agentic Operating System](../index.md) — governance layer and skills
