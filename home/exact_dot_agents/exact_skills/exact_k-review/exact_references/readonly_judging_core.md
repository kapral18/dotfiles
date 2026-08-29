# Judging Core (Surface-Agnostic)

- Mode files and `shared_rules.md` reference this file; do not duplicate these sections elsewhere.
- Delivery-agnostic: no GitHub, SCSI, or delivery rules.
- Surfaces needing PR/SCSI/GitHub-delivery rules layer them via `shared_rules.md`.
- The findings pipeline (Coverage Checklist, Post-Review Lens, Findings-Set Audit, Post-Review Stage, Verify-and-Fix Loop) lives in `judging_pipeline.md`.

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

In review-only PR mode for someone else's work, keep the worktree read-only, use the harness to verify claims when safe, and surface missing or inadequate state-machine coverage as a test gap when risk remains.

## Async-Derived State Gate (Run On Values Resolved Over Time)

Trigger: the diff adds or changes a conditional, default injection, reset, or visibility gate whose predicate derives from an asynchronously-resolved source — promise resolution, readiness callbacks, fetched collections, subscription emissions, lazy initialization.

A settled-value-only analysis is incomplete: such values pass through intermediate states (pending, undefined, partial) that production reaches and idealized tests skip.

1. **Value timeline:** enumerate the derived value's states across time — initial evaluation, every transition, final settlement —
   and name every consumer keyed on it: conditionals, dependency arrays, effect re-runs, callback/memo identity, persisted defaults.
   Verify each consumer tolerates each transition, not just each settled state.
   An identity-sensitive consumer (a callback listed in a dependency array) treats a value flip as a new input even when the boolean meaning looks stable.
2. **Transition probe:** a static read cannot clear behavior that depends on such a value _changing_.
   Before a clean verdict on an affected surface, verify the transition by executing or simulating it (disposable test/probe per SOP `3.6`), or report the surface as unverified instead of cleared.
   Green suites do not substitute: tests that set the source to its settled value synchronously never exercise the transition.
3. **Failure vs empty:** for gates fed by fetched collections or remote state, discovery failure and confirmed-empty are distinct inputs;
   a gate mapping both to one outcome silently converts an outage into a valid-empty result.
   Verify the failure path settles differently, or that accepting the merge is explicit.

## Context-Divergence Gate (Run On Shared Paths Serving Multiple Contexts)

Trigger: the diff changes a path exercised by more than one execution context —
deployment tier, environment, license/subscription level, tenant, feature-flag state, user role, or platform.

A fix verified in one context says nothing about sibling contexts sharing the same code path;
these failures read as successful fixes from inside the reviewed context.

1. **Enumerate sibling contexts:** name every context that reaches the changed path, from scope-level evidence outward (config reads, flag checks, tier/license predicates, role guards).
2. **Classify each context:** preserved, changed, or newly-reachable, anchored against base behavior.
   A context whose behavior flipped silently is HIGH even when the reviewed context's change is correct.
3. **Verify or surface:** exercise at least one intended and one preserved context per SOP `3.5`;
   when a preserved context cannot be verified statically, report it unverified instead of cleared.

## Scale-Behavior Gate (Run On Collection And Volume Operations)

Trigger: any loop, batch, recursion, query construction, or collection transformation lies on a changed path —
regardless of whether the diff looks performance-sensitive.
The trigger is structural, not appearance-based: production volume is invisible in a diff hunk.

1. **State production n:** name the realistic production scale of the data this operation consumes (items, rows, requests, bytes).
   If unknown, treat as `Unknown` and resolve before clearing.
2. **Trace at boundaries:** walk the operation at 0, 1, typical n, and an order of magnitude beyond;
   check for per-item work moved into loops, queries issued per iteration, unbounded accumulation, and result sets rendered or serialized without a bound.
3. **Report honestly:** a scale hazard here is a finding with severity set by consequence;
   calling the scale safe requires naming the bound, not absence of observation.

## Deletion-Safety Audit (Run On Any Removal)

Trigger: the diff deletes files, exports, symbols, or behavior.

Signals include: `git diff --diff-filter=D --stat`, removed `export`s, deleted functions/branches.

Before calling a deletion safe, verify each item and report a one-line deletion ledger:

- **No live references:** `rg` the deleted symbol/file/path across the repo and public barrels/index files;
  confirm zero live importers/callers.
- **Public surface:** deleted exports are removed from barrels and not part of a published package entry point still consumed downstream.
- **Behavior parity:**
  - every deleted behavior is intentionally dropped (user-approved per SOP `2.1`) or demonstrably replaced; name each replacement
- **Tests:** deleted tests were migrated, or removed only because the code they covered is gone;
  coverage still exists for behavior that remains after the diff.
- **Base comparison:**
  - for branch-heavy/stateful deletions, compare against base behavior buckets, see State-Machine Verification Gate, and classify each difference as intended/unexpected
- **Disclosure:** meaningful deleted infrastructure is reflected in the PR description (Summary/Fix), not silently dropped.

## Replacement/Migration Parity Gate (Run On Replacements And Test Migrations)

Trigger: the diff deletes or stops using an implementation/test/helper and adds a replacement for the same behavior.

Definitions:

- **Old implementation:** the base-branch code/test/helper that the diff deletes, unregisters, or stops calling.
- **Replacement:** the head-branch code/test/helper now covering the same behavior.
- **Candidate:** a possible review finding before this gate classifies it.

Before a candidate can become review feedback:

1. **Map old to replacement:** identify old and replacement entry points, helper side effects, assertions/checkpoints, setup/cleanup, permissions, wiring, and runtime assumptions.
   - For every explicitly set behavior/style/spacing/layout property, name where the replacement re-establishes it (component, prop, or default) or prove it is intentionally dropped.
     "I did not observe a regression" is not evidence the property is preserved;
     absence-of-observation never substitutes for naming the replacement's contract.
   - A migration handing a property to the target component (e.g. local CSS replaced by a shared component default) is only `preserved_limitation`/`scope_expansion`/intended-replacement after citing the target's contract (static source proof) or verifying it live.
     Until then the candidate stays unclassified, not dropped.
2. **Assign exactly one classification:**
   - `parity_gap`: old behavior or coverage existed and the replacement omits or weakens it.
   - `new_regression`: the replacement adds a failure mode the old implementation did not have.
   - `preserved_limitation`: the old implementation had the same limitation and the replacement does not worsen it.
   - `scope_expansion`: the PR body, linked issue, user request, or reviewer request explicitly requires stronger behavior/coverage than the old implementation provided.
   - `prose_drift`: only prose, counts, or docs disagree; implementation behavior and coverage remain equivalent.
3. **Keep/drop rule:**
   - Keep `parity_gap`, `new_regression`, and `scope_expansion` as review findings when evidence supports them.
   - Drop `preserved_limitation` from review feedback. Do not ask the author to fix it in this PR.
   - Drop `prose_drift` from code-review feedback.
     If it matters to reviewers, handle it as PR-level prose feedback, not as an implementation finding.
4. **Verification rule:** run live UI, heavy runtime probes, or delegated findings audit only for a kept candidate when source-level evidence cannot decide keep/drop; skip them for `preserved_limitation` or `prose_drift`.
   - The live-UI skip only applies once step 1's evidence bar is met.
     Never drop a UI-visual candidate (spacing, alignment, layout, visual styling) on an unproven classification and then cite that drop as why live UI was unnecessary — that inverts cause/effect.
     If classification rests on a UI-visual property you have neither traced to the replacement's contract nor verified live, the candidate is unproven: settle with static proof or live UI before classifying; do not skip because it was dropped.

## Historical Archaeology Gate (Code Provenance & Evolution)

Trigger: modifying, replacing, or deleting existing non-trivial logic, guards, conditionals, fallback branches, or legacy infrastructure.

Code encodes history; static search sees current syntax, not past bugs, CVEs, or edge cases that shaped it.
In large repos, keep probes targeted and line-bounded rather than running whole-file blame:

- **Targeted line archaeology:** probe only high-uncertainty or non-obvious modified logic; always bound line ranges and depth:
  `git blame -L <start>,<end> <base> -- <path>` or `git log -n 5 -L <start>,<end>:<path>` to find introducing commit and PR context (`gh pr view`, `gh issue view`).
  Never run unbounded whole-file blame in massive repos.
- **Unwritten invariant check:** discover whether a modified guard/fallback was introduced to fix a subtle bug, race condition, backward-compatibility requirement, or upstream quirk.
- **Regression reintroduction:** verify whether the diff inadvertently removes or weakens a guard previously added to fix a past defect.
- **Classify & act:**
  - _intentional obsolescence:_ past reason no longer applies; document why in review/PR.
  - _accidental regression:_ re-opens a historical bug or breaks a hard-won invariant; classify as HIGH.
  - _historical drift:_ refactor preserves past invariant under cleaner architecture.

## Semantic-Projection & Sibling-Consumer Gate

Trigger: semantic delta changes how a domain relationship is interpreted, projected, stored, rendered, compared, filtered, or serialized.

Audit co-located consumers that project, compare, or transform that same concept:

- **Projection symmetry:** when one projection changes, verify parallel projections reflect the same semantic mapping.
- **Bi-directional consistency:** verify read vs write, serialize vs deserialize, and encode vs decode paths handle all known variants and edge cases symmetrically.
- **Delta divergence:** classify any case where sibling consumers apply diverging semantic deltas to the same input space as HIGH (broken invariant / silent behavioral split).

## Product-Flow Lens (Run When The Diff Touches User-Facing Flows)

Trigger: the diff changes UI components, routes, user-state management, or API handlers that serve a UI.

Walk each affected user path as finding generation: trigger -> loading -> result (success or error).

- **Flow completeness:** the user can finish the workflow end-to-end; no path dead-ends without a next action or feedback.
- **Action acknowledgment:** every user-initiated action has loading, success, empty, and error states handled.
- **State consistency:** no stale data after an action, no optimistic update that never reconciles; refresh preserves the expected state.
- **Error experience:** failures produce a meaningful message; the user can recover without losing work;
  transient errors (network, timeout) are distinguishable from permanent ones.
- **Behavior expectations:** no surprises for a user who knows the existing product;
  labels, button text, and placeholders accurately describe what happens; new behavior is discoverable.
- **Data visibility:** the user sees the expected data after an action; pagination, sorting, and filtering stay consistent after the change;
  column sort keys and filter predicates match rendered cell labels and groupings.

These heuristics generate candidates. Verify per Truth Validation Framework; broken user paths are HIGH severity.

## Signal-Quality Gate (Run On Alerting/Monitoring/Analytics Logic)

Trigger: the diff changes alerting rules, monitoring queries, thresholds, statistical aggregations, telemetry pipelines, or prompts generating such queries.

Judge the signal, not just the code:

- **False positives:** conditions causing firing when nothing is wrong (noise, baseline shifts, seasonality).
- **False negatives:** conditions causing silence when something is wrong (slow-burn, partial/single-node failures).
- **Statistical soundness:** valid comparisons, right rate denominators, sparse percentile handling, aligned time buckets.
- **Actionability:** fired signal gives triage context; correlated signals do not storm from one root cause.

Prefer executing queries against representative data in safe runtimes; otherwise label analysis a hypothesis.
Domain specifics (syntax, mappings, scale limits) come from verified domain overlays.

## Systemic-Risk Checks (Run When The Diff Crosses Module Or Deploy Boundaries)

Trigger: the diff changes public API contracts, persisted data, cross-module/package imports, or behavior that ships through a staged/rolling rollout.

- **Rolling-deploy coexistence:** old and new code run against the same data/API mid-deploy;
  verify both directions survive version boundaries.
- **Rollout gating:** when conventions expect incremental rollout, verify proper gating (without adding unrequested flags per SOP `2.1`).
- **Circular dependencies:** verify the change does not introduce package/module cycles.
- **Blast radius:** state what breaks if wrong and pair each risk with concrete mitigation.

Deletion-Safety and Parity gates own deletions/replacements; this section covers deploy/coupling risk.

## Severity Definitions (Internal Only; Do Not Prefix Comments With These)

- CRITICAL: security vulnerability, data loss/corruption, authz/authn bypass, crash, or unsafe migration.
- HIGH: user-visible bug, broken invariant, serious performance regression, or high operational risk.
- MEDIUM: maintainability risk, unclear behavior, missing tests for a risky change, or non-trivial tech debt.
- LOW: small improvements, clarity, naming/style consistency (true nits).
