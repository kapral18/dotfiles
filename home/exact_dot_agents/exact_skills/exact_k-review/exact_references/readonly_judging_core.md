# Judging Core (Surface-Agnostic)

- Mode files and `shared_rules.md` reference this file; do not duplicate these sections elsewhere.
- Delivery-agnostic: no GitHub, SCSI, or delivery rules.
- Surfaces needing PR/SCSI/GitHub-delivery rules layer them via `shared_rules.md`.
- The findings pipeline (Coverage Checklist, Post-Review Lens, Findings-Set Audit, Post-Review Stage, Verify-and-Fix Loop) lives in `judging_pipeline.md`.

## Conditional Gate Loading

Before judging each changed path or plan claim, evaluate every trigger below against its evidence and the assigned scope.
Reference paths below are relative to `~/.agents/skills/k-review/references/`.
For every matching gate, load its named reference before applying that gate or clearing the affected surface.
If applicability is uncertain, inspect the relevant source/plan first; unresolved applicability requires loading the gate, not skipping it.
An assigned check requiring a gate must load its reference before that check, including direct role entry;
conditional checks retain their stated triggers.
Load each reference once while its full text remains in context; apply only the gates whose triggers or assigned checks match.
After compaction, reopen this index and references needed by the current phase;
a completed-gate ledger entry is not a replacement for instructions needed by a new or reopened finding.

## Truth Validation Framework

Use in every non-trivial review.

- Treat every claim as a hypothesis until verified.
- A rationale is also a claim: verify actual runtime/code behavior, not explanations.
- Self-consistency check: when a rationale claims an input/file/condition is irrelevant, perturb it and confirm outcome stability.
- A static read proves what source says, not what the system does; verify runtime behavior whenever candidate keep/drop depends on observed state.
- **Diff-boundary tunnel vision is forbidden:** reviewing diff hunks in isolation without inspecting surrounding context, caller trees, and sibling consumers is never justified across any review tier (light, standard, or deep).
  The diff is the source for what changed (delta) and commentability; full files and caller trees (via local `rg`, symbol lookup, or SCSI) give the ground truth for system behavior.
- For diffs not proven mechanical-only, reconstruct semantic delta: old/new rule, intended/preserved differences, evidence.
  Missing/extra/unproven rows are candidates until refuted.
- Establish base invariants first (SCSI when indexed; otherwise `git show <base>:<path>` + local `rg`), then validate PR/branch reality (diff + full file reads).
- Evaluate the diff as a state and contract boundary; simulate behavior across universal failure primitives:
  caller/callee contract asymmetry, test oracle/mock fidelity gaps, compositional fault cascades in batch/collection processing, temporal/async hazards, projection/mapping divergence, silent error degradation, and predicate negation/boundary-swap mutations — for each changed condition, enumerate its inverted and off-by-one forms and name one observable consequence each.
- When evaluating a proposed change: prefer smallest repro in `/tmp` or smallest safe experiment in worktree.
- If you changed code in an iteration cycle, re-run repo quality gates (lint + type_check + tests).
- Keep an evidence log per comment/thread: base behavior, semantic delta, tests run, observations.

## Candidate Refutation Ladder (Run Before Reporting Or Acting)

Owned by the agent that decides keep/drop and acts (k-light-review, direct review modes, or a controller).
Fan-out: the dedicated adversarial lane (cross-family preferred at equal capability, SOP §3.7) owns this pass;
read-only finder lanes only return candidates plus a reachability statement and do not self-refute.

A candidate survives only when a genuine refutation attempt fails with evidence.
Default to `undecidable`, not `keep`, when the deciding evidence is genuinely out of reach.
Attempt refutation in this order and stop at the first decisive result:

1. **Claim truth:** read the cited code and its callers/callees on the actual diff; does the claimed behavior occur?
   Construct the explicit trace from initial state and input through the boundary failure to the unhandled state;
   drop candidates that rest on abstract speculation without a concrete execution path.
2. **Reachability:** is the claimed path reachable (inputs, flags, permissions)?
   An unreachable path refutes the severity even when the observation is textually correct. State reachability for every kept finding.
3. **Severity:** does the evidence support the assigned severity under the definitions below, or a different one?
   Correct in both directions.
4. **Proposed fix:** would the fix behave as claimed without introducing a new problem?
   Compare fix delta with requested delta; broader delta is a candidate, not implementation detail.
5. **Already covered:** is the concern already handled elsewhere in the diff or base? Cite where.

Self-refutation catches unreachable paths, inflated severity, and weak fixes, but lacks cross-family independence.
Use fan-out when available; self-refutation stands in only when fan-out is unavailable.

## State-Machine Verification Gate

Apply SOP `### 3.6 State-Machine Verification` to reviewed behavior that is stateful, parser-like, branch-heavy, or dependent on ordered conditions.

Examples include parsers, tokenizers, formatters, routing/matching logic, retry/workflow loops, permission matrices, compatibility-sensitive branching, multi-flag control flow.

Required reference: `judging_state.md` (matching heading).

## Async-Derived State Gate (Run On Values Resolved Over Time)

Trigger: the diff adds or changes a conditional, default injection, reset, or visibility gate whose predicate derives from an asynchronously-resolved source — promise resolution, readiness callbacks, fetched collections, subscription emissions, lazy initialization.

Required reference: `judging_state.md` (matching heading).

## Context-Divergence Gate (Run On Shared Paths Serving Multiple Contexts)

Trigger: the diff changes a path exercised by more than one execution context —
deployment tier, environment, license/subscription level, tenant, feature-flag state, user role, or platform.

Required reference: `judging_state.md` (matching heading).

## Scale-Behavior Gate (Run On Collection And Volume Operations)

Trigger: any loop, batch, recursion, query construction, or collection transformation lies on a changed path —
regardless of whether the diff looks performance-sensitive.
The trigger is structural, not appearance-based: production volume is invisible in a diff hunk.

Required reference: `judging_state.md` (matching heading).

## Deletion-Safety Audit (Run On Any Removal)

Trigger: the diff deletes files, exports, symbols, or behavior.

Required reference: `judging_change.md` (matching heading).

## Replacement/Migration Parity Gate (Run On Replacements And Test Migrations)

Trigger: the diff deletes or stops using an implementation/test/helper and adds a replacement for the same behavior.

Required reference: `judging_change.md` (matching heading).

## Historical Archaeology Gate (Code Provenance & Evolution)

Trigger: modifying, replacing, or deleting existing non-trivial logic, guards, conditionals, fallback branches, or legacy infrastructure.

Required reference: `judging_change.md` (matching heading).

## Semantic-Projection & Sibling-Consumer Gate

Trigger: semantic delta changes how a domain relationship is interpreted, projected, stored, rendered, compared, filtered, or serialized.

Required reference: `judging_change.md` (matching heading).

## Product-Flow Lens (Run When The Diff Touches User-Facing Flows)

Trigger: the diff changes UI components, routes, user-state management, or API handlers that serve a UI.

Required reference: `judging_product.md` (matching heading).

## Signal-Quality Gate (Run On Alerting/Monitoring/Analytics Logic)

Trigger: the diff changes alerting rules, monitoring queries, thresholds, statistical aggregations, telemetry pipelines, or prompts generating such queries.

Required reference: `judging_product.md` (matching heading).

## Systemic-Risk Checks (Run When The Diff Crosses Module Or Deploy Boundaries)

Trigger: the diff changes public API contracts, persisted data, cross-module/package imports, or behavior that ships through a staged/rolling rollout.

Required reference: `judging_product.md` (matching heading).

## Severity Definitions (Internal Only; Do Not Prefix Comments With These)

- CRITICAL: security vulnerability, data loss/corruption, authz/authn bypass, crash, or unsafe migration.
- HIGH: user-visible bug, broken invariant, serious performance regression, or high operational risk.
- MEDIUM: maintainability risk, unclear behavior, missing tests for a risky change, or non-trivial tech debt.
- LOW: small improvements, clarity, naming/style consistency (true nits).
