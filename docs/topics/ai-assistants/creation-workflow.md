---
sidebar_position: 6
title: Creation workflow
---

Creation and [review](reviews/index.md) share the root-owned `Scope → Understand → Produce → Verify → Deliver` lifecycle. Skills provide task mechanics and criteria, not nested phase graphs.

Resolve material intent and authorization before implementation. An already-approved request needs no second approval ceremony; reading the final report is delivery, not another gate. Commits, pushes and publication retain their separate authority requirements.

Ordinary freeform implementation does not have to enter this formal flow. Verification stays inline by default; `k-proof` and `,proof` add a smaller repo-external receipt only for an explicit receipt request, an auditable risky effect, or a named handoff/resume consumer.

## Task state and implementation packet

| Artifact                           | Role                                                                                                | Mutation rule                                                                                      |
| ---------------------------------- | --------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `/tmp/specs/<pwd>/<topic>.txt`     | Compact task handoff: requirements, decisions, stage, active/terminal packets and evidence pointers | Update as evidence or user decisions change; never treat a summary as proof                        |
| `/tmp/specs/<pwd>/<topic>.spec.md` | The `k-spec` implementation packet: scope, intended/preserved behavior and planned final checks     | Revise only for a material changed premise or decision; preserve the user's authorization boundary |

The topic records current work; durable cross-session learning remains in `,ai-kb`. Neither artifact grants commit or publication authority.

The packet traces requirements to the user's request and source evidence. Acceptance checks are planned, not run merely to approve the packet. Existing baseline failure evidence may inform Understand; it is not a mandatory red-check ceremony for every criterion.

The `k-spec` skill records the packet path in the active topic so a continuation can find it without rebuilding the contract.

An empirical fork may need a targeted prototype; do not create one automatically. A material mid-build contradiction returns the concrete decision to the root instead of silently changing scope. See [Choose your flow](scenarios.md).

## Using it

Lifecycle:

```text
Scope       intent, owned targets, authorization, material user decisions
Understand  missing facts, necessary baseline evidence, approach and final check plan
Produce     approved implementation, tests/docs, integration and formatting
Verify      frozen candidate; deduplicated checks and selected strong judgment
Deliver     results, evidence and authorized publication only
```

## `/k-build` responsibilities

| Stage      | Responsibility                                                                                     | Completion condition                                                                                                    |
| ---------- | -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Scope      | Strong root and any necessary user decision                                                        | Approved target, scope, compatibility intent and authority are clear                                                    |
| Understand | Strong research where needed; root settles decisions                                               | Missing material facts resolved and final acceptance plan defined                                                       |
| Produce    | Implementation-band workers for substantial settled edits; deterministic tools for mechanical work | Owned artifacts integrated and formatted; workers return produced/blocked, not green                                    |
| Verify     | Root-owned checks plus selected strong review/refute questions                                     | Actual frozen artifact and shared evidence support passed/failed/blocked criteria; applicable UI proof is included here |
| Deliver    | Root                                                                                               | Truthful outcome, evidence and remaining blockers; no automatic repair, post-review or convergence                      |

Keep criterion status and evidence pointers in the task's existing state. Production uses pending/produced/blocked; only final Verify certifies passed/failed/blocked. Large work does not automatically require a separate proof ledger.

Reviewers consume complete shared check receipts and actual relevant artifacts. They do not rerun successful checks for independence or certify another reviewer's verdict. Deep/high-risk work preserves strong artifact review and adversarial challenge as distinct questions within this one stage. A no-delegation request keeps the work inline and does not weaken the criteria.

## The criteria-verifier lane

Worker contract: [`k-build/references/criteria-verifier.md`](../../../home/exact_dot_agents/exact_skills/exact_k-build/exact_references/readonly_criteria-verifier.md).

This optional final framing judges each acceptance criterion, intended differences and preserved behavior against the frozen artifact and existing receipts. It returns one consolidated supported/unsupported/unknown result with exact evidence; it does not edit, repeat checks, broaden into unrelated audits or start a repair loop.

Per-harness profiles are rendered through the same review-model resolver the review verifier uses. Cursor, Copilot, Codex, Pi, and OMP ship a `k-agent-criteria-verifier` profile; Antigravity defines the role dynamically and invokes its `pro` tier.

Claude runs the lane degraded on the session model with refutation framing, reported as `families=same (degraded)`. This mirrors the adversarial-verifier convention in [Cross-harness subagents](subagents.md).

## Live-UI proof within final Verify

When any acceptance criterion's evidence is visual — a `judgment:` criterion naming a screenshot/visual comparison, or an in-scope UI-facing change with a stated visual goal — `/k-build` runs the proof-mode contract, [`k-ui-capture/references/proof-mode.md`](../../../home/exact_dot_agents/exact_skills/exact_k-ui-capture/exact_references/readonly_proof-mode.md), owned by the [`k-ui-capture`](../../../home/exact_dot_agents/exact_skills/exact_k-ui-capture/readonly_SKILL.md) skill.

It is the creation-side sibling of the review flow's `k-agent-live-ui-review`: same runtime machinery, opposite direction. `k-agent-live-ui-review` compares PR/head against base to find regressions; the proof-mode contract verifies the **built** runtime head-only against its **intended visual** and captures the proof media set — screenshots for static deltas, videos for interactive ones — that proves it. Inventory items carry a comparison frame (`baseline` vs `intra-change`) and embed text must pass the claim map (every named behavior maps to an adequate asset).

Both share one mode-neutral contract — [`k-review/references/live-ui-runtime.md`](../../../home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_live-ui-runtime.md) — for target-packet resolution, Playwriter preflight, readiness, runtime start, the data/setup ladder, screenshot artifacts, and the runtime safety boundary.

Each mode file adds only its oracle, comparison model, and return shape.

The proof-mode contract runs **inline** in `/k-build`, which already holds Playwriter and local/dev mutation permissions, so it needs no isolated subagent profile.

It returns a per-criterion `met` / `unmet` / `blocked` verdict with the captured evidence. An `unmet` or `blocked` result is reported in the root's final outcome; it does not send the worker back into implementation.

The controller reports the proof manifest. Each proof set lives in its own distinct `/tmp/<folder-name>/` folder, so `k-compose-pr` can upload and embed the media.

Windows/VirtualBox coverage is a separate manual skill, [`k-live-ui-windows`](../../../home/exact_dot_agents/exact_skills/exact_k-live-ui-windows/), connecting Playwriter to a guest browser over CDP through a host NAT port-forward. It is never auto-triggered by either mode; load it by hand only when the user explicitly asks for Windows/VirtualBox verification this turn.

A final verification failure is reported with evidence. Repair within existing scope and authority follows SOP §3.5 (a failed check is not a new permission checkpoint); explicitly requested `k-converge` runs its declared-exit loop (mutation probes and fresh refuters until a dry round) instead. There is no implicit retry budget or post-review cleanup stage.
