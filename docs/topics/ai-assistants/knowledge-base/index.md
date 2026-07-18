---
title: Agent Memory
---

# Agent Memory

Two memory layers serve different jobs: **topic context** resumes current work, while the **durable KB** carries reusable lessons across sessions.

| Need                        | System         | Surface                               | Details                                        |
| --------------------------- | -------------- | ------------------------------------- | ---------------------------------------------- |
| Resume the current work     | Hook memory    | `/tmp/specs/...` + `,agent-memory`    | [Hook memory](hook-memory.md)                  |
| Reuse a verified lesson     | Durable KB     | `~/.local/share/ai-kb/` + `,ai-kb`    | [AI knowledge base](ai-kb.md)                  |
| Understand automatic recall | Runtime wiring | shared KB + harness hooks and plugins | [Runtime recall wiring](cross-agent-memory.md) |

## Quickstart

```bash
# Session topic (ephemeral — not durable lessons)
,agent-memory status --session-id <id>
,agent-memory select <topic> --session-id <id>          # bind session to bucket
,agent-memory note gotcha "..." --ref scripts/foo.py:42   # task-scoped; harvest later

# Durable KB (verified reusable insights only)
,ai-kb search "<actual task query>" --limit 5 --json
,ai-kb remember --title "..." --body "..." --kind gotcha --scope project \
                --workspace "$(pwd)" --source "path:line" --confidence 0.9 --domain chezmoi
,ai-kb harvest --session-id <id>                          # read-only candidates from worklog
```

## Boundaries

| System                      | Use for                               | Not for           |
| --------------------------- | ------------------------------------- | ----------------- |
| `,agent-memory`             | session topic, worklog/evidence trace | durable lessons   |
| `,ai-kb`                    | verified facts, gotchas, recipes      | transient scratch |
| SCSI / semantic-code-search | repository code                       | agent memory      |

Proof receipts are separate: `,proof` tracks criteria, evidence, assessments, and blockers in repo-external agent-proof state only for a requested, auditable, or named-handoff receipt.

## Related

- [Palantír orchestrator](../palantir.md) — close-out routing for durable findings
- [The Agentic Operating System](../index.md) — governance layer and skills
