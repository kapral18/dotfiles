---
sidebar_position: 2
title: Choose your flow
---

# Choose your flow (scenario router)

Every AI-development scenario this setup supports is routed by what you want to do, not by which subsystem implements it. Each row names the flow, how you start it, and where to go deeper.

The [pivot map](#pivot-map) places those mechanics in one root-owned lifecycle. Selecting another skill does not create another agent, verification pass or approval gate.

The major flows have hands-on playbooks — what to type, what you'll see, what to answer at each gate — under Flow playbooks in the sidebar. Table rows link to a playbook where one exists.

## Mental model

Two invocation kinds matter throughout:

| Invocation kind      | Meaning                                                                                                                |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Model-invoked skills | Fire on their own when your prompt matches, such as "debug this".                                                      |
| Manual skills        | Fire only when you type them, such as `/k-build` or `/k-deep-review`. High-blast-radius flows are deliberately manual. |

## Build something

| You want to…                                   | Flow                                                                                | Start it                                            | Deeper                                                                     |
| ---------------------------------------------- | ----------------------------------------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------------- |
| Turn an idea/bug into a testable contract      | `k-spec` → compact packet with planned final acceptance checks                      | "develop a spec for …" (model-invoked)              | [Playbook](flows/spec-and-build.md) · [architecture](creation-workflow.md) |
| Implement an approved contract in this session | `/k-build` — production followed by one integrated final verification               | `/k-build` after approving a packet                 | [Playbook](flows/spec-and-build.md) · [architecture](creation-workflow.md) |
| Diagnose or fix a reported defect              | `k-diagnosing-bugs` — evidence-driven diagnosis; implementation only when requested | "debug/diagnose this" or "fix this" (model-invoked) | [Playbook](flows/debug-a-bug.md)                                           |
| Answer a design question cheaply               | `k-prototype` — throwaway logic probe or 3 UI variants                              | "prototype this" (model-invoked)                    | [Playbook](flows/prototype-and-design.md)                                  |
| Shape a module boundary or seam                | `k-codebase-design` — deep-module vocabulary, design-it-twice                       | fires when designing interfaces                     | row in [skills](skills/repo-workflow-and-code-intelligence.md)             |
| Get requirements out of your head              | `k-interview-me` — one fork-closing question at a time                              | `/k-interview-me` (manual)                          | row in [skills](skills/memory-and-orchestration.md)                        |
| Be told what's worth building next             | `k-improve-local` / `-branch` / `-targeted` / `-codebase` — exactly one proposal    | `/k-improve-…` (manual)                             | rows in [skills](skills/memory-and-orchestration.md)                       |

## Check something

| You want to…                                    | Flow                                                                                                                           | Start it                                                                   | Deeper                                                                                 |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Focused review of low-risk local changes        | `k-light-review` — one read-only final judgment using shared evidence                                                          | `/k-light-review` (also model-invoked)                                     | [Playbook](flows/review-your-changes.md)                                               |
| Full review of a PR or risky change             | `k-review` — modes: pr_review, pr_fix, local_changes, plan_review                                                              | "review PR #N" (model-invoked)                                             | [Playbook](flows/review-your-changes.md) · [architecture](reviews/index.md)            |
| Deep review of a PR or risky change             | `/k-deep-review` — scoped reviewer roster, adversarial verify (cross-family preferred), live UI                                | `/k-deep-review` (manual)                                                  | [Playbook](flows/review-your-changes.md) · [topology](reviews/deep-review-topology.md) |
| Review a plan/spec as the requested deliverable | `k-review` plan mode — judges the contract, not code; not a mandatory build gate                                               | "review this plan/packet"                                                  | [Review workflow](reviews/index.md)                                                    |
| Produce a durable receipt for freeform work     | `k-proof` — repo-external criteria/evidence/assessment ledger with a finalized seal                                            | explicit receipt, auditable risky effect, or named handoff/resume consumer | row in [skills](skills/memory-and-orchestration.md)                                    |
| Verify a change actually works end-to-end       | `verify`-style live drive; UI via `k-playwriter`, or `k-ui-capture` for media proof (screenshots/videos) of an intended visual | "verify this works" / "screenshot the UI for the PR"                       | rows in [skills](skills/external-tools-and-media.md)                                   |
| Review what an agent produced (you as reviewer) | staged-diff reading discipline                                                                                                 | —                                                                          | [Reviewing agent diffs](reviewing-diffs.md)                                            |

## Understand something

| You want to…                         | Flow                                                                | Start it                                 | Deeper                                                          |
| ------------------------------------ | ------------------------------------------------------------------- | ---------------------------------------- | --------------------------------------------------------------- |
| Learn how this codebase works        | `k-walkthrough` — evidence-anchored tour or ASCII architecture map  | `/k-walkthrough` (manual)                | [Playbook](flows/understand-code.md)                            |
| Investigate an external repo/library | `k-public-sources` — clone to `/tmp`, read source, answer from code | "figure out how X works" (model-invoked) | [Playbook](flows/understand-code.md)                            |
| Find code by concept, not keyword    | `k-semantic-code-search` (SCSI)                                     | fires on conceptual search               | [MCP servers](mcp.md)                                           |
| Drive an interactive terminal safely | `k-tmux` — isolated sockets, pane capture, explicit targets         | fires on tmux/pane/session work          | row in [skills](skills/repo-workflow-and-code-intelligence.md)  |
| Find duplication / dead exports      | `k-jscpd` / `k-knip`                                                | fires during cleanup work                | rows in [skills](skills/repo-workflow-and-code-intelligence.md) |

## Communicate something

| You want to…                                  | Flow                                                                                         | Start it                                                                                          | Deeper                                                                                     |
| --------------------------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Draft or prepare an issue                     | `k-compose-issue` — issue text + publication packet, no side effects                         | "draft an issue for …"                                                                            | [Playbook](flows/ship-text.md)                                                             |
| Draft a PR body                               | `k-compose-pr` — evidence-backed Test Plan gate                                              | "draft the PR text"                                                                               | [Playbook](flows/ship-text.md)                                                             |
| Prove a built UI looks right, for a PR        | `k-ui-capture` — head-only live check + before/after screenshots/videos, gated GitHub upload | "verify this UI" / `/k-ui-capture`; its proof-mode reference fires in `/k-build` / `k-compose-pr` | [architecture](creation-workflow.md) · row in [skills](skills/external-tools-and-media.md) |
| Help reviewers before they open the diff      | `k-present-pr` — self-contained HTML review-readiness map                                    | `/k-present-pr` (manual)                                                                          | [Playbook](flows/ship-text.md)                                                             |
| Post, reply, react, or edit a canvas in Slack | `k-slack` — Slack MCP mechanics: live-id resolution, §3.8 preflight, single send, read-back  | "post this to #channel" / "reply in that thread"; reads never load it                             | [row in skills](skills/external-tools-and-media.md#k-slack)                                |
| Anything a human will read                    | `k-communication` owns tone; publication always gated                                        | loaded automatically before drafting                                                              | [Side-effect gates](system-prompt/side-effect-gates.md)                                    |

## Cross-cutting rules

- Durable memory (`,ai-kb`) retains automatic staged recall and one final learning batch; no per-turn scribe or leaf memory orchestration. See [Agent memory](knowledge-base/index.md).
- `k-proof` records sealed receipts for narrowly gated freeform work; ordinary verification stays inline.
- The code-quality family loads itself on implementation edits.
- Kibana/Elastic work gets the domain overlay; see [Elastic and Kibana](skills/elastic-and-kibana.md).

## Pivot map

Only the active root owns transitions. A skill supplies mechanics for the current stage; it does not restart the lifecycle. Empty stages need no ceremony.

```text
Scope → Understand → Produce → Verify → Deliver
          │             │         │         └─ results; approved publication only
          │             │         └─ selected review depth + shared final checks
          │             └─ authorized implementation, tests, docs and formatting
          └─ source/diagnosis/design mechanics; prototype only for a material empirical fork

Review depth: k-light-review OR k-review OR explicitly requested /k-deep-review
Not a sequence of reviews over one another.
```

When to pivot, concretely:

- **spec → prototype and back.** A fork you cannot close by asking, such as "which ordering feels right?", is empirical. Build the throwaway, observe, and let the verdict — not an opinion — close the fork in the packet. The prototype is deleted; the decision survives in the packet's Context line.
- **/k-build → spec (re-gate).** Mid-build evidence contradicting the packet, such as a wrong premise or wrong scope, stops the build. Revise the packet and re-approve. Never let a build quietly implement a different spec than the one you signed.
- **Select review depth before Verify.** Low-risk local work uses light review; PR/base-context or risky/stateful work uses standard review with appropriate lenses. Explicit deep review retains strong artifact review and adversarial challenge on distinct questions. Reuse shared evidence; do not escalate a completed review into a reviewer-of-reviewer chain. A final failure is reported, not an automatic workflow restart.
- **Diagnosis and design.** Use design mechanics in Understand when an in-scope seam/design question must be settled for the requested fix. An architectural observation does not authorize a post-fix redesign or broader audit.
- **anything → k-compose-issue.** Work that should be recorded rather than done now — a bug found mid-review, a packet worth filing upstream — becomes issue text; publication stays human-gated.

## Efficiency defaults

- Choose sufficient scope from evidence and risk, then complete one final Verify stage. Direct work does not automatically append a review skill.
- Preserve strong judgment for substantial research and final review/refutation; use the implementation band for settled edits and deterministic tools for mechanical work.
- Category model/effort and isolation follow [Model tiering](model-tiering.md) and [the worker contract](subagents.md). Independent ready packets may run concurrently; no leaf owns orchestration, private QA or another worker's certification.
