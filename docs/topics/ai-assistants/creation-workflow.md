---
sidebar_position: 6
title: Creation workflow
---

# Creation workflow (spec → build / Ralph)

The creation-side counterpart to the [review workflow](reviews/index.md): the same rigor primitives — evidence-gated phases, fixed return shapes, adversarial verification, a completion gate — applied to building things instead of judging them. The steering model is **two human gates**: approve the contract before execution, read the report after it. Everything between runs hands-free.

Ordinary freeform implementation does not have to enter this formal flow. For that main path, the `proof` skill and `,proof` CLI provide a smaller repo-external criteria/evidence ledger only when a hard trigger fires.

## The two artifacts (memory vs contract)

| Artifact                           | Role                                                                                                     | Mutation rule                                                       |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `/tmp/specs/<pwd>/<topic>.txt`     | Conversation memory: what we currently believe the user wants. Hook-injected at session start.           | Rewritten freely as the intent loop converges. Allowed to be wrong. |
| `/tmp/specs/<pwd>/<topic>.spec.md` | Contract snapshot: what counts as done and how to prove it. Consumed by `/build` and `,ralph go --spec`. | Frozen at approval; changing it is a premise correction + re-gate.  |

The intent spec remembers the discussion; the packet is a signed order. The packet is never a mechanical transform of the intent spec: nothing enters it on the `.txt`'s word alone — every criterion is re-derived from evidence and its check is run once, observed red, before it may appear. After approval the flow is one-way: Ralph snapshots the spec into the run manifest, `/build`'s ledger holds evidence, so later `.txt` drift cannot retro-poison an in-flight run.

The `spec` skill writes a `packet:` pointer line into `<topic>.txt` so session-start injection tells a fresh session the contract exists, and requires a named topic first on default branches (the `session-<id>` fallback would strand the packet).

Two pivots keep the contract honest in both directions: empirical forks route out to `prototype` (the verdict returns to the packet), and mid-build premise contradictions route back to gate 1. Both — and all flow-to-flow movement — are mapped in [Choose your flow](scenarios.md).

## Lifecycle

```text
idea/issue
  └─ spec skill: necessity check → fork-closing interview (interview-me discipline,
     empirical forks → prototype) → acceptance criteria with run-once RED checks
     → packet written + shown
        └─ [HUMAN GATE 1: approve packet]
            ├─ /build ............ in-session hands-free implementation
            ├─ ,ralph go --spec .. detached run, same contract
            ├─ compose-issue ..... publishable issue text + publication packet
            └─ review (plan mode)  adversarial review of the packet itself
                └─ [HUMAN GATE 2: read the report]
```

## `/build` phase topology

| Phase                 | Owner                    | Gate                                                                                                                                                |
| --------------------- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Spec gate          | controller + human       | packet exists, checks red-proven; explicit approval                                                                                                 |
| 2. Plan               | controller               | per-step verification defined; Ownership Gate over touched paths                                                                                    |
| 3. Execute            | controller               | criteria ledger updated per step; never past a red step; §3.3 reset on 2×                                                                           |
| 4. Mechanical gates   | controller               | repo lint/type/tests discovered, run, looped to green                                                                                               |
| 5. Live-UI proof      | `ui-proof` (inline)      | visual criteria verified head-only against the built runtime; each proof set captured to its own distinct `/tmp/<folder-name>/` and opened/provided |
| 6. Adversarial verify | `criteria-verifier` lane | checks re-run from clean tree; refutation verdicts + scope audit                                                                                    |
| 7. Post-review stage  | controller               | four dimensions over the implementation diff                                                                                                        |
| 8. Report             | controller + human       | mandated output block; completion gate                                                                                                              |

The **criteria ledger** is the run's spine: one row per acceptance criterion (`red` / `green` / `judgment-met` / `judgment-unmet` / `blocked`), each with command-level evidence, plus a verification verdict (`confirmed` / `refuted` / `undecidable`). Verdicts are evidence, not decisions — the controller flips a row only after checking the refutation addresses the row's actual claim.

## The criteria-verifier lane

Worker contract: [`build/references/criteria-verifier.md`](../../../home/exact_dot_agents/exact_skills/exact_build/exact_references/readonly_criteria-verifier.md) — refutation order (claim truth → criterion truth → reachability → durability), a scope audit against the packet's binding out-of-scope list, and missing-criteria candidates.

Per-harness profiles are rendered from the same `agent_review_models` registry the review verifier uses: cursor, copilot, gemini, codex, and pi ship a `criteria-verifier` profile; Claude runs the lane degraded on the session model with refutation framing, reported as `families=same (degraded)` — mirroring the adversarial-verifier convention in [Cross-harness subagents](subagents.md).

## Live-UI proof (phase 5)

When any acceptance criterion's evidence is visual — a `judgment:` criterion naming a screenshot/visual comparison, or an in-scope UI-facing change with a stated visual goal — `/build` runs the [`ui-proof`](../../../home/exact_dot_agents/exact_skills/exact_ui-proof/readonly_SKILL.md) skill. It is the creation-side sibling of the review flow's `live-ui-review`: same runtime machinery, opposite direction. `live-ui-review` compares PR/head against base to find regressions; `ui-proof` verifies the **built** runtime head-only against its **intended visual** and captures the screenshot set that proves it.

Both share one mode-neutral contract — [`agent-review/references/live-ui-runtime.md`](../../../home/exact_dot_agents/exact_skills/exact_agent-review/exact_references/readonly_live-ui-runtime.md) — for target-packet resolution, Playwriter preflight, readiness, runtime start, the data/setup ladder, screenshot artifacts, and the runtime safety boundary; each mode file adds only its oracle, comparison model, and return shape. `ui-proof` runs **inline** in `/build` (which already holds Playwriter and local/dev mutation permissions), so it needs no isolated subagent profile. It returns a per-criterion `met` / `unmet` / `blocked` verdict; the controller sets the ledger's `judgment-met`/`judgment-unmet` row from it (an `unmet` returns to phase 3 like a red step), opens/provides the screenshot folder, and reports the screenshot manifest (each screenshot/pair/set in its own distinct `/tmp/<folder-name>/` folder with folder-open/provided status) so `compose-pr` can embed the shots.

## Ralph as the detached form

`,ralph go --spec <file>` consumes the packet's JSON handoff block (the planner's Shape A schema) and skips the planner entirely; `--goal` defaults from the spec, and `--plan-only`/`--workflow` are rejected as superseded. The machine-check floor holds in both forms: Ralph executes every criterion `check` each iteration (demotion mechanics in [State and runtime](ralph/state-and-runtime.md)); `/build` re-runs the checks at verification and blocks its completion gate on red rows. A `,ralph replan` re-enters the planner and replaces the operator spec — steering returns to Ralph at that point.

See [Ralph orchestrator](ralph/index.md) for the loop itself and [State and runtime](ralph/state-and-runtime.md) for where check results land (`manifest.criteria_check_results`, `summary.md`).
