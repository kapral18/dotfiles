# Judging Core (Surface-Agnostic)

- Mode files and `shared_rules.md` reference this file; keep these sections defined here only.
- Delivery-agnostic: no GitHub, SCSI, or delivery rules.
- Surfaces needing PR/SCSI/GitHub-delivery rules layer them via `shared_rules.md`.

## Truth Validation Framework

Use in every non-trivial review.

- Treat every claim as a hypothesis until verified.
- A rationale is also a claim: verify actual runtime/code behavior, not explanations.
- Self-consistency check: when a rationale claims an input/file/condition is irrelevant, perturb it and confirm outcome stability.
- A static read proves what source says, not what the system does; verify runtime behavior whenever candidate keep/drop depends on observed state.
- **Diff-boundary tunnel vision is forbidden:** reviewing diff hunks in isolation without inspecting surrounding context, caller trees, and sibling consumers is never justified across any review tier (light, standard, or deep).
  Always expand beyond the diff: read full enclosing files, trace callers/callees (via local `rg`, symbol lookup, or SCSI), and audit how changed behavior impacts preexisting surrounding contracts.
- Establish base invariants first (SCSI when indexed; otherwise `git show <base>:<path>` + local `rg`), then validate PR/branch reality (diff + full file reads).
- Evaluate the diff as a state and contract boundary; simulate behavior across universal failure primitives:
  caller/callee contract asymmetry, test oracle/mock fidelity gaps, compositional fault cascades in batch/collection processing, temporal/async hazards, projection/mapping divergence, and silent error degradation.
- When evaluating a proposed change: prefer smallest repro in `/tmp` or smallest safe experiment in worktree.
- If you changed code in an iteration cycle, re-run repo quality gates (lint + type_check + tests).
- Keep an evidence log per comment/thread: base behavior, delta, tests run, observations.

## Candidate Refutation Ladder (Run Before Reporting Or Acting)

Owned by the agent that decides keep/drop and acts (k-light-review, direct review modes, or a controller).
Fan-out: the dedicated adversarial lane (cross-family preferred at equal capability, SOP §3.5) owns this pass;
Read-only finder lanes only return candidates plus a reachability statement; self-refutation is owned elsewhere.

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
5. **Already covered:** is the concern already handled elsewhere in the diff or base? Cite where.

Self-refutation catches unreachable paths, inflated severity, and weak fixes, but lacks cross-family independence.
Use fan-out when available; self-refutation stands in only when fan-out is unavailable.

## State-Machine Verification Gate

Apply SOP `### 3.4.1 State-Machine Verification` to reviewed behavior that is stateful, parser-like, branch-heavy, or dependent on ordered conditions.

Examples include parsers, tokenizers, formatters, routing/matching logic, retry/workflow loops, permission matrices, compatibility-sensitive branching, multi-flag control flow.

In review-only PR mode for someone else's work, keep the worktree read-only, use the harness to verify claims when safe, and surface missing or inadequate state-machine coverage as a test gap when risk remains.

## Deletion-Safety Audit (Run On Any Removal)

Trigger: the diff deletes files, exports, symbols, or behavior.

Signals include: `git diff --diff-filter=D --stat`, removed `export`s, deleted functions/branches.

Before calling a deletion safe, verify each item and report a one-line deletion ledger:

- **No live references:** `rg` the deleted symbol/file/path across the repo and public barrels/index files;
  confirm zero live importers/callers.
- **Public surface:** deleted exports are removed from barrels and not part of a published package entry point still consumed downstream.
- **Behavior parity:**
  - every deleted behavior is intentionally dropped (user-approved per SOP `2.0`) or demonstrably replaced; name each replacement
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

Trigger: the diff changes how a domain concept, state enum, data bucket, or entity property is classified, partitioned, mapped, or formatted.

Audit co-located consumers that project, compare, or transform that same concept:

- **Projection symmetry:** when one projection of a concept is updated (e.g. formatting, categorization, or normalization), verify that parallel projections (sorting/ordering comparators, filter predicates, search matchers, equality checks, serialization, or export) reflect the identical semantic mapping.
- **Bi-directional consistency:** verify read vs write, serialize vs deserialize, and encode vs decode paths handle all known variants and edge cases symmetrically.
- **Classification divergence:** classify any case where sibling consumers apply diverging partition rules to the same input space as HIGH (broken invariant / silent behavioral split).

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
- **Rollout gating:** when conventions expect incremental rollout, verify proper gating (without adding unrequested flags per SOP `2.0`).
- **Circular dependencies:** verify the change does not introduce package/module cycles.
- **Blast radius:** state what breaks if wrong and pair each risk with concrete mitigation.

Deletion-Safety and Parity gates own deletions/replacements; this section covers deploy/coupling risk.

## Coverage Checklist (Do Not Skip)

On PR surfaces, first apply the CI Coverage Gate (`pr_common.md`).

A finding-class is exempt only when a present PR CI check genuinely catches it:

- First verify the check exists and covers the class; then CI will flag it — leave it to CI without re-checking or commenting on it.
- Keep in scope every class where CI is loosened or absent (e.g. a backport).

Non-PR surfaces have no PR CI to dedup against:

- local-changes
- k-light-review

Check every class below for non-PR surfaces: security; logic/correctness/invariants; data-loss risk; performance regressions;
test gaps (especially risky changes without tests, and expectations restating generated/spec-derived data instead of an independent oracle);
docs; maintainability/complexity; true nits.

## Severity Definitions (Internal Only; Do Not Prefix Comments With These)

- CRITICAL: security vulnerability, data loss/corruption, authz/authn bypass, crash, or unsafe migration.
- HIGH: user-visible bug, broken invariant, serious performance regression, or high operational risk.
- MEDIUM: maintainability risk, unclear behavior, missing tests for a risky change, or non-trivial tech debt.
- LOW: small improvements, clarity, naming/style consistency (true nits).

## Post-Review Lens (The Four Dimensions)

Subject: the **fix diff** a review just produced (see Post-Review Stage).

These four dimensions are the only **canonical** ones: name them exactly, keeping each one's name, boundary, and shape as written.

1. **Redundancy** — the change repeats something existing:
   - re-implements an existing helper; re-states a rule already stated elsewhere; adds a path/branch/config that is already present
2. **Verbosity** — the change is bloated beyond the task: extra code/prose, comments that restate code, ceremony, or over-explanation.
3. **Semantic + logical duplication** — two places express the **same meaning or behavior** via different text (not literal copy-paste):
   - parallel branches that should be one; a rule stated two ways; divergent-but-equivalent logic;
     this is the subtle axis literal-clone detectors (`jscpd`) miss
4. **Gaps** — incomplete change:
   - dead code the change stranded; a co-edit-set member left unupdated (doc/diagram/census drift, or sibling sort/filter/persistence consumer left on old mapping); a half-applied rename; a referenced file/symbol that does not exist

For each dimension, anchor any finding in evidence: exact file + location, duplicate's other location, stranded symbol.

Assert a hygiene problem only after pointing at it.

## Findings-Set Audit (Run Before Final Refutation Or Acting)

Subject: candidate findings and proposed fixes — not the fix diff (Post-Review Stage) or original diff.
Owned by the deciding agent (k-light-review, the direct review modes, or a controller).
In deeper fan-out orchestration, keep this in the controller by default and delegate to `findings-auditor` only for non-trivial sets.

Before final adversarial refutation, fixing, drafting, or presenting findings, run the four dimensions (Post-Review Lens) over the finding set:

- **Redundancy / semantic + logical duplication:** collapse two findings with the same root cause or anchor region into one;
  present each issue exactly once, under one wording.
- **Verbosity:** trim finding text and proposed fixes to the smallest form that still carries the evidence.
- **Gaps:** name any finding asserted without an exact anchor or without a decisive verification path, and either anchor it or drop it.

Also check each surviving finding for **actionability** (is the smallest fix concrete?) and **overengineering** (does the proposed fix exceed the proved problem?).
Merging duplicate findings is a deduplication task, never evidence that the underlying issue is unnecessary; keep the merged candidate.

## Post-Review Stage (Run On Any Change-Producing Flow)

Trigger: a flow has applied fixes and mechanical quality gates are green.
Applied-fix flows include local-changes verify-and-fix, PR-fix self-fixes, k-light-review, or any pass that edited the working tree.
Mechanical quality gates: lint, type_check, tests. Subject: the **fixes themselves** (the changes the review just made).

1. **Derive the fix diff.** Scope to what this pass changed; original diff under review is not the subject.
2. **Run the four dimensions** over that fix diff: redundancy, verbosity, semantic + logical duplication, gaps.
3. **Resolve in the working tree.** Fix the smallest correct change now. In read-only contexts, surface a finding + proposed fix.
4. **Re-gate if edited.** If post-review fixes touched code, re-run lint + type_check + tests.
5. **Fixed point.** Re-run this Post-Review Stage after cleanup.
   Repeat until the four dimensions return clean, or until a verified blocker/Requirements Reset stops the loop.

This stage closes the loop: lint/types/tests prove fixes _work_; the four dimensions prove fixes are _clean_.

## Verify-and-Fix Loop (Self-Authored Change-Producing Review)

Shared verify-and-fix spine for self-authored, fix-authorized review surfaces. Each surface sets scope and base-context stance first.
Read-only lanes report precise fixes for the parent to apply instead of editing.

1. **Build the findings queue.** Walk the whole diff against the Coverage Checklist, ordered by severity.
2. **Audit the set.** Run the Findings-Set Audit over candidate findings and proposed fixes.
3. **Final refutation.**
   Run the Candidate Refutation Ladder or the available adversarial-verifier lane over the audited set;
   keep only survivors, record reachability, and drop refuted/unverified findings.
4. **Fix each finding** highest severity first: verify from evidence, apply the smallest correct change, and commit/push only when asked.
   For non-trivial or ambiguous fixes, state options and proceed with the recommended default unless the user intervenes.
5. **Quality gates.** Run repo lint + type_check + tests; fix until green or report what remains and why.
6. **Post-Review Stage.** Run it over this pass's fix diff, then re-run quality gates if cleanup touched code.
7. **Fixed point.** Re-run this verify-and-fix loop over the current scoped diff.
   Repeat until no new surviving findings or hygiene findings remain; stop only for a verified blocker, Requirements Reset, or user fork.
