---
sidebar_position: 2
title: Choose your flow
---

# Choose your flow (scenario router)

Every AI-development scenario this setup supports, routed by what you want to do — not by which subsystem implements it. Each row names the flow, how you start it, and where to go deeper. The [pivot map](#pivot-map) below shows how to move between flows mid-work; that mobility is the point of having many flows.

The major flows have hands-on playbooks — what to type, what you'll see, what to answer at each gate — under Flow playbooks in the sidebar; table rows link to a playbook where one exists.

Two invocation kinds matter throughout: **model-invoked** skills fire on their own when your prompt matches ("debug this"), while **manual** skills fire only when you type them (`/build`, `/agent-review`) — the high-blast-radius flows are deliberately manual.

## Build something

| You want to…                                     | Flow                                                                           | Start it                                                 | Deeper                                                                      |
| ------------------------------------------------ | ------------------------------------------------------------------------------ | -------------------------------------------------------- | --------------------------------------------------------------------------- |
| Turn an idea/bug into a testable contract        | `spec` → packet with red-proven acceptance checks                              | "develop a spec for …" (model-invoked)                   | [Playbook](flows/spec-and-build.md) · [architecture](creation-workflow.md)  |
| Implement a contract hands-free, in this session | `/build` — criteria ledger, adversarial verify, 2 human gates                  | `/build` after approving a packet                        | [Playbook](flows/spec-and-build.md) · [architecture](creation-workflow.md)  |
| Implement a contract detached, off your desk     | `,ralph go --spec <file>` — planner skipped, checks machine-run                | write the packet's JSON block to a file, run the command | [Playbook](flows/ralph-run.md) · [architecture](ralph/index.md)             |
| Fire-and-forget from one sentence                | `,ralph go --goal "…"` — planner authors the contract                          | one shell command; observe via `prefix+A`                | [Playbook](flows/ralph-run.md) · [architecture](ralph/state-and-runtime.md) |
| Fix a reported defect                            | `diagnosing-bugs` — tight red loop before any theory, 6 phases                 | "debug/diagnose this" (model-invoked)                    | [Playbook](flows/debug-a-bug.md)                                            |
| Answer a design question cheaply                 | `prototype` — throwaway logic probe or 3 UI variants                           | "prototype this" (model-invoked)                         | [Playbook](flows/prototype-and-design.md)                                   |
| Shape a module boundary or seam                  | `codebase-design` — deep-module vocabulary, design-it-twice                    | fires when designing interfaces                          | row in [skills](skills/repo-workflow-and-code-intelligence.md)              |
| Get requirements out of your head                | `interview-me` — one fork-closing question at a time                           | `/interview-me` (manual)                                 | row in [skills](skills/memory-and-orchestration.md)                         |
| Be told what's worth building next               | `improve-local` / `-branch` / `-targeted` / `-codebase` — exactly one proposal | `/improve-…` (manual)                                    | rows in [skills](skills/memory-and-orchestration.md)                        |

## Check something

| You want to…                                      | Flow                                                                    | Start it                             | Deeper                                                                                  |
| ------------------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------ | --------------------------------------------------------------------------------------- |
| Quick audit of your own uncommitted work          | `light-review` — proportional depth, fixes in place                     | `/light-review` (also model-invoked) | [Playbook](flows/review-your-changes.md)                                                |
| Full review of a PR or risky change               | `review` — modes: pr_review, pr_fix, local_changes, plan_review         | "review PR #N" (model-invoked)       | [Playbook](flows/review-your-changes.md) · [architecture](reviews/index.md)             |
| Maximum-rigor multi-agent review                  | `/agent-review` — angle lanes, cross-family adversarial verify, live UI | `/agent-review` (manual)             | [Playbook](flows/review-your-changes.md) · [topology](reviews/agent-review-topology.md) |
| Adversarial review of a plan/spec before building | `review` plan mode — judges the contract, not code                      | "review this plan/packet"            | [Review workflow](reviews/index.md)                                                     |
| Verify a change actually works end-to-end         | `verify`-style live drive; UI via `playwriter`                          | "verify this works"                  | rows in [skills](skills/external-tools-and-media.md)                                    |
| Review what an agent produced (you as reviewer)   | staged-diff reading discipline                                          | —                                    | [Reviewing agent diffs](reviewing-diffs.md)                                             |

## Understand something

| You want to…                         | Flow                                                             | Start it                                 | Deeper                                                          |
| ------------------------------------ | ---------------------------------------------------------------- | ---------------------------------------- | --------------------------------------------------------------- |
| Learn how this codebase works        | `walkthrough` — evidence-anchored tour or ASCII architecture map | `/walkthrough` (manual)                  | [Playbook](flows/understand-code.md)                            |
| Investigate an external repo/library | `research` — clone to `/tmp`, read source, answer from code      | "figure out how X works" (model-invoked) | [Playbook](flows/understand-code.md)                            |
| Find code by concept, not keyword    | `semantic-code-search` (SCSI)                                    | fires on conceptual search               | [MCP servers](mcp.md)                                           |
| Find duplication / dead exports      | `jscpd` / `knip`                                                 | fires during cleanup work                | rows in [skills](skills/repo-workflow-and-code-intelligence.md) |

## Communicate something

| You want to…                             | Flow                                                    | Start it                             | Deeper                                                  |
| ---------------------------------------- | ------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------- |
| Draft an issue                           | `compose-issue` — text only, no side effects            | "draft an issue for …"               | [Playbook](flows/ship-text.md)                          |
| Draft a PR body                          | `compose-pr` — evidence-backed Test Plan gate           | "draft the PR text"                  | [Playbook](flows/ship-text.md)                          |
| Help reviewers before they open the diff | `present-pr` — self-contained HTML review-readiness map | `/present-pr` (manual)               | [Playbook](flows/ship-text.md)                          |
| Anything a human will read               | `communication` owns tone; publication always gated     | loaded automatically before drafting | [Side-effect gates](system-prompt/side-effect-gates.md) |

Cross-cutting: durable memory (`,ai-kb`) recalls before non-trivial work and persists verified lessons — [Agent memory](knowledge-base/index.md); the code-quality family loads itself on implementation edits; Kibana/Elastic work gets the domain overlay — [Elastic and Kibana](skills/elastic-and-kibana.md).

## Pivot map

Flows hand off to each other at defined points; pivoting is expected, not an exception. The heavier arrows are contracts (the target consumes an artifact); the lighter ones are escalations (you stop one flow and enter another).

```text
                    interview-me
                         │ intent clear, needs a contract
                         ▼
   prototype ◄──────── spec ────────► review (plan mode)
   empirical fork        │  ▲            adversarial packet review
   verdict returns ──────┘  │ premise correction / uncheckable criterion
   to the packet            │ (build returns you here)
                ┌────────┼─────────┐
                ▼        ▼         ▼
             /build   ,ralph go   compose-issue / compose-pr
             in-session  --spec      publishable text
                │        │ replan → planner re-enters, spec superseded
                ▼        ▼
             light-review over the result … escalates to → review → /agent-review

   diagnosing-bugs ──"no correct seam / architectural cause"──► codebase-design
        │ writing the regression test                              │ design settled
        ▼                                                          ▼
   code-quality-tests ◄────────────────────────────────────────────┘
```

When to pivot, concretely:

- **spec → prototype and back.** A fork you cannot close by asking ("which ordering feels right?") is empirical: build the throwaway, observe, and the verdict — not an opinion — closes the fork in the packet. The prototype is deleted; the decision survives in the packet's Context line.
- **spec → /build vs → Ralph.** Same contract, different runtime: `/build` when the work benefits from your session's context or you want blockers surfaced in-conversation; Ralph when you want it off your desk, parallel, or survivable past this session. You can do both across a topic — they read the same packet format.
- **/build → spec (re-gate).** Mid-build evidence contradicting the packet (wrong premise, wrong scope) stops the build; revise the packet and re-approve. Never let a build quietly implement a different spec than the one you signed.
- **Ralph → planner (replan).** `,ralph replan` on an operator-spec run hands contract authorship back to Ralph's planner — use it when the run parks on questions whose answers change the plan's shape.
- **light-review → review → /agent-review.** Escalate when the target turns out to be a PR/others' code, needs base-branch context, or is risky/stateful (light→full), and to `/agent-review` when you want independent lanes and cross-family adversarial verification instead of one reviewer's judgment. Escalation is mid-pass: stop, switch, don't half-do the heavy machinery in the light flow.
- **diagnosing-bugs → codebase-design.** Two triggers: no correct seam exists for the regression test (the architecture is preventing the bug from being locked down), or the post-mortem answer to "what would have prevented this?" is architectural. Hand off after the fix, with specifics.
- **anything → compose-issue.** Work that should be recorded rather than done now — a bug found mid-review, a packet worth filing upstream — becomes issue text; publication stays human-gated.

## Efficiency defaults

- Smallest flow that fits: direct SOP work → `light-review` to check it. Reach for `spec`/`/build`/Ralph when the work is big enough that a contract pays for itself, and for `/agent-review` when the change is big enough to warrant independent readers.
- One packet in flight per topic; parallel streams belong on separate topics (or separate Ralph runs — they isolate per run id).
- Trust the machine floor: packet checks are executed, not read ([mechanics](ralph/state-and-runtime.md)) — your attention belongs at the two human gates, not in between.
