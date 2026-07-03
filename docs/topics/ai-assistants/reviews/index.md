---
title: Review Workflow
---

# Review Workflow

This section covers the agent reviewing your diff. The inverse loop is [Reviewing agent diffs](../reviewing-diffs.md).

| Navigation slice                                                        | Owns                                                                                   |
| ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| [Agent-review topology](agent-review-topology.md)                       | `/agent-review` phases, worker ownership, live UI handoff, controller responsibilities |
| [Base context and truth validation](base-context-and-truth.md)          | SCSI/base-branch context, strict verification, PR intake, necessity audit              |
| [Post-review and light review](post-review-and-light-review.md)         | four-dimension hygiene lens and proportional self-review                               |
| [Replies, publication, and history](replies-publication-and-history.md) | reply style, router behavior, human-visible gate, deletion/history safeguards          |

## Direction map

| Direction                   | Tooling                                                                                                                                                            |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Agent reviews your diff     | `review` skill: [`home/exact_dot_agents/exact_skills/exact_review`](../../../../home/exact_dot_agents/exact_skills/exact_review)                                   |
| Agent reviews a plan/spec   | `review` plan mode (`references/plan_review.md`) — judges a design doc or [spec packet](../creation-workflow.md) before any implementation; no diff, no authorship |
| You review the agent's diff | [Reviewing agent diffs](../reviewing-diffs.md)                                                                                                                     |

Use this section when continuing a review, addressing review threads, rechecking PR-related changes, or deciding whether the lighter in-place review is enough.

## Related

- [The Agentic Operating System](../index.md) — governance layer and skills
- [Ralph orchestrator](../ralph/index.md) — reviewer/re-reviewer roles can invoke this skill through domain review policies
