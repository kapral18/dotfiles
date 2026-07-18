---
sidebar_position: 6
title: Creation workflow
---

# Creation workflow (spec → build / Palantír)

The creation-side counterpart to the [review workflow](reviews/index.md) applies the same rigor primitives to building things instead of judging them: evidence-gated phases, fixed return shapes, adversarial verification, and a completion gate.

The steering model is **two human gates**: approve the contract before execution, then read the report after it. Everything between runs hands-free.

Ordinary freeform implementation does not have to enter this formal flow. Verification stays inline by default; `k-proof` and `,proof` add a smaller repo-external receipt only for an explicit receipt request, an auditable risky effect, or a named handoff/resume consumer.

## The two artifacts (memory vs contract)

| Artifact                           | Role                                                                                                                  | Mutation rule                                                       |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `/tmp/specs/<pwd>/<topic>.txt`     | Conversation memory: what we currently believe the user wants. Hook-injected at session start.                        | Rewritten freely as the intent loop converges. Allowed to be wrong. |
| `/tmp/specs/<pwd>/<topic>.spec.md` | Contract snapshot: what counts as done and how to prove it. Consumed by `/k-build` and `,palantir summon --criteria`. | Frozen at approval; changing it is a premise correction + re-gate.  |

The intent spec remembers the discussion; the packet is a signed order.

The packet is never a mechanical transform of the intent spec. Nothing enters it on the `.txt`'s word alone: every criterion is re-derived from evidence and its check is run once, observed red, before it may appear.

After approval the flow is one-way. Palantír snapshots the criteria into the legion manifest, and `/k-build`'s ledger holds evidence, so later `.txt` drift cannot retro-poison in-flight work.

The `k-spec` skill writes a `packet:` pointer line into `<topic>.txt` so session-start injection tells a fresh session the contract exists.

On default branches, `k-spec` requires a named topic first because the `session-<id>` fallback would strand the packet.

Two pivots keep the contract honest in both directions: empirical forks route out to `k-prototype`, where the verdict returns to the packet; mid-build premise contradictions route back to gate 1. Both — and all flow-to-flow movement — are mapped in [Choose your flow](scenarios.md).

## Using it

Lifecycle:

```text
idea/issue
  └─ spec skill: necessity check → fork-closing interview (interview-me discipline,
     empirical forks → prototype) → acceptance criteria with run-once RED checks
     → packet written + shown
        └─ [HUMAN GATE 1: approve packet]
            ├─ /k-build ............ in-session hands-free implementation
            ├─ ,palantir summon ... detached legion, same criteria
            ├─ k-compose-issue ... publishable issue text + publication packet
            └─ review (plan mode)  adversarial review of the packet itself
                └─ [HUMAN GATE 2: read the report]
```

Choose `/k-build` when the work benefits from the current session's context or blockers should surface in-conversation. Choose `,palantir summon "<goal>" --criteria '<json>'` when the same criteria should run in a detached legion.

## `/k-build` phase topology

| Phase                 | Owner                    | Gate                                                                                                                                                |
| --------------------- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Spec gate          | controller + human       | packet exists, checks red-proven; explicit approval                                                                                                 |
| 2. Plan               | controller               | per-step verification defined; Ownership Gate over touched paths                                                                                    |
| 3. Execute            | controller               | criteria ledger updated per step; never past a red step; §3.3 reset on 2×                                                                           |
| 4. Mechanical gates   | controller               | repo lint/type/tests discovered, run, looped to green                                                                                               |
| 5. Live-UI proof      | `k-ui-proof` (inline)    | visual criteria verified head-only against the built runtime; each proof set captured to its own distinct `/tmp/<folder-name>/` and opened/provided |
| 6. Adversarial verify | `criteria-verifier` lane | checks re-run from clean tree; refutation verdicts + scope audit                                                                                    |
| 7. Post-review stage  | controller               | four dimensions over the implementation diff                                                                                                        |
| 8. Report             | controller + human       | mandated output block; completion gate                                                                                                              |

The **criteria ledger** is the run's spine. It has one row per acceptance criterion (`red` / `green` / `judgment-met` / `judgment-unmet` / `blocked`), each with command-level evidence, plus a verification verdict (`confirmed` / `refuted` / `undecidable`).

Verdicts are evidence, not decisions. The controller flips a row only after checking the refutation addresses the row's actual claim.

## The criteria-verifier lane

Worker contract: [`k-build/references/criteria-verifier.md`](../../../home/exact_dot_agents/exact_skills/exact_k-build/exact_references/readonly_criteria-verifier.md).

The lane owns refutation order (claim truth → criterion truth → reachability → durability), a scope audit against the packet's binding out-of-scope list, and missing-criteria candidates.

Per-harness profiles are rendered from the same `agent_review_models` registry the review verifier uses. Cursor, Copilot, Gemini, Codex, and Pi ship a `criteria-verifier` profile.

Claude runs the lane degraded on the session model with refutation framing, reported as `families=same (degraded)`. This mirrors the adversarial-verifier convention in [Cross-harness subagents](subagents.md).

## Live-UI proof (phase 5)

When any acceptance criterion's evidence is visual — a `judgment:` criterion naming a screenshot/visual comparison, or an in-scope UI-facing change with a stated visual goal — `/k-build` runs the [`k-ui-proof`](../../../home/exact_dot_agents/exact_skills/exact_k-ui-proof/readonly_SKILL.md) skill.

It is the creation-side sibling of the review flow's `live-ui-review`: same runtime machinery, opposite direction. `live-ui-review` compares PR/head against base to find regressions; `k-ui-proof` verifies the **built** runtime head-only against its **intended visual** and captures the screenshot set that proves it.

Both share one mode-neutral contract — [`k-agent-review/references/live-ui-runtime.md`](../../../home/exact_dot_agents/exact_skills/exact_k-agent-review/exact_references/readonly_live-ui-runtime.md) — for target-packet resolution, Playwriter preflight, readiness, runtime start, the data/setup ladder, screenshot artifacts, and the runtime safety boundary.

Each mode file adds only its oracle, comparison model, and return shape.

`k-ui-proof` runs **inline** in `/k-build`, which already holds Playwriter and local/dev mutation permissions, so it needs no isolated subagent profile.

It returns a per-criterion `met` / `unmet` / `blocked` verdict. The controller sets the ledger's `judgment-met`/`judgment-unmet` row from it; an `unmet` returns to phase 3 like a red step.

The controller opens/provides the screenshot folder and reports the screenshot manifest. Each screenshot/pair/set lives in its own distinct `/tmp/<folder-name>/` folder with folder-open/provided status, so `k-compose-pr` can embed the shots.

Windows/VirtualBox coverage is a separate manual skill, [`k-live-ui-windows`](../../../home/exact_dot_agents/exact_skills/exact_k-live-ui-windows/), connecting Playwriter to a guest browser over CDP through a host NAT port-forward. It is never auto-triggered by either mode; load it by hand only when the user explicitly asks for Windows/VirtualBox verification this turn.

## Palantír as the detached form

`,palantir summon "<goal>" --criteria '<json>'` consumes the packet's criteria JSON and starts one tmux-native legion for the effort.

The criteria must already be red-proven by the spec flow; Palantír does not turn unchecked prose into a completion gate.

The machine-check floor holds in both forms. Palantír's `verify` stage executes every criterion command and only a zero exit is green; `/k-build` re-runs checks inside its own verification phase and blocks its completion gate on red rows.

A verify failure sends bounded evidence back to `implement`, retries up to the configured budget, and then parks the legion in `holding` for a human answer or sent word.

See [Palantír orchestrator](palantir.md) for the stage machine, handshake files, dashboard, and state layout.
