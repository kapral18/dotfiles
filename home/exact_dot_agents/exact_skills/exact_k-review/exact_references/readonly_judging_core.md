# Judging Core (Surface-Agnostic)

- Mode files and `shared_rules.md` reference this file; do not duplicate these sections elsewhere.
- Delivery-agnostic: no GitHub, SCSI, or delivery rules.
- Surfaces needing PR/SCSI/GitHub-delivery rules layer them via `shared_rules.md`.

## Truth Validation Framework

Use in every non-trivial review.

- Treat every claim as a hypothesis until verified.
- A rationale is also a claim: a PR description, code comment, commit message, or reviewer's summary says what someone believes drove the change, not what the change does.
  Verify behavior, not explanation.
- Self-consistency check: when a rationale claims an input/file/condition is irrelevant, perturb exactly that and confirm the outcome is stable; if the outcome changes, rationale is not the real driver and the finding needs re-investigation.
- A static read (reading source, searching the tree) proves what the source says, not what the system does.
  When candidate keep/drop depends on observed/runtime behavior, static evidence is a hypothesis, not proof;
  verify runtime behavior whenever available, because a static read can contradict the system.
  (E.g. a source search indicated no tab tooltips; the live UI rendered four.)
- Establish base invariants first (SCSI when indexed; otherwise `git show <base>:<path>` + local `rg`).
- Validate PR/branch reality second (local diff + file reads).
- When evaluating a proposed change (review suggestion / reviewer request):
  - prefer the smallest reproduction in `/tmp` when possible
  - otherwise run the smallest safe experiment in the worktree
- If you changed code as part of an iteration cycle, re-run the repo's quality gates:
  - lint + type_check + tests (discover the correct commands from the repo; do not guess).
- Keep an evidence log per comment/thread: what base does, what changed, what you tested, and what you observed.

## Candidate Refutation Ladder (Run Before Keeping Any Finding)

Owned by the agent that decides keep/drop and acts (k-light-review, direct review modes, or a controller).
Fan-out: the dedicated cross-family adversarial lane owns this pass; read-only finder lanes only return candidates plus a reachability statement and do not self-refute.

A candidate survives only when a genuine refutation attempt fails with evidence.
Default to `undecidable`, not `keep`, when the deciding evidence is genuinely out of reach.
Attempt refutation in this order and stop at the first decisive result:

1. **Claim truth:** read the cited code and its callers/callees on the actual diff; does the claimed behavior occur?
2. **Reachability:** is the claimed path reachable (inputs, flags, permissions)?
   An unreachable path refutes the severity even when the observation is textually correct. State reachability for every kept finding.
3. **Severity:** does the evidence support the assigned severity under the definitions below, or a different one?
   Correct in both directions.
4. **Proposed fix:** would the fix behave as claimed without introducing a new problem?
5. **Already covered:** is the concern already handled elsewhere in the diff or base? Cite where.

Self-refutation catches unreachable paths, inflated severity, and fixes that do not hold, but lacks the cross-family independence of the fan-out adversarial lane.
Do not treat self-refutation as a substitute for that lane where fan-out is available.

## State-Machine Verification Gate

Use for reviewed behavior that is stateful, parser-like, branch-heavy, or dependent on ordered conditions.

Examples include parsers, tokenizers, formatters, routing/matching logic, retry/workflow loops, permission matrices, compatibility-sensitive branching, multi-flag control flow.

- Before calling the change final, merge-ready, or a review concern resolved, build/inspect a disposable harness under `/tmp/state-machine-verification/<pwd>/<topic>/<slug>/`.
- The harness must include `manifest.json` with worktree, topic, slug, target files/symbols, branch, base/head refs when relevant, requested behavior, and compatibility intent.
- Model explicitly: states, transitions, inputs, terminal actions.
- Cover: existing behavior buckets, requested behavior, boundary/malformed inputs, regression-sensitive examples.
- Compare implementation against an independent model/state table, not just itself.
- When behavior should be preserved:
  - compare against base and classify each difference as intended or unexpected
- In review-only PR mode for someone else's work:
  - keep code read-only, use the harness to verify claims when safe, and surface missing/inadequate state-machine coverage as a test gap when risk remains

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
4. **Verification rule:** do not run live UI, heavy runtime probes, or delegated findings audit for `preserved_limitation` or `prose_drift`.
   Run them only for a kept candidate when source-level evidence cannot decide keep/drop.
   - The live-UI skip only applies once step 1's evidence bar is met.
     Never drop a UI-visual candidate (spacing, alignment, layout, visual styling) on an unproven classification and then cite that drop as why live UI was unnecessary — that inverts cause/effect.
     If classification rests on a UI-visual property you have neither traced to the replacement's contract nor verified live, the candidate is unproven: settle with static proof or live UI before classifying; do not skip because it was dropped.

## Historical-Rationale Gate (Deleting/Replacing Long-Lived Infra)

Trigger: removing/replacing a custom/legacy stack, helper predating current infra, anything called "obsolete" or "legacy", or anything framed as "why does this exist".

Understand the origin before the removal is final.

- **Trace origin:** `git log --follow --oneline -- <path>` and `git blame <base> -- <path>` (or `git log -L` for a function) to find introducing commit(s).
- **Link intent:** open the offending PR(s)/issue(s) (`gh pr view`, `gh issue view`) to learn the original reason.
- **Classify:** was the behavior being removed (a) the original intended purpose, or (b) drift/side effect that later infra made obsolete?
- **Decide narrative:**
  - if removal corrects historical drift, the PR `## Root Cause` must state the original reason and why it no longer applies
  - if it removes still-needed behavior, stop
  - that is not a safe deletion

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
- **Data visibility:** the user sees the expected data after an action; pagination, sorting, and filtering stay consistent after the change.

These heuristics generate candidates; they do not verify them.
Verify per the Truth Validation Framework: when a runtime check is available, a static walkthrough of a user path is a hypothesis, not proof.
A broken or dead-end user path is a user-visible bug (HIGH under the severity definitions below).

## Signal-Quality Gate (Run On Alerting/Monitoring/Analytics Logic)

Trigger: the diff changes alerting rules, monitoring queries, thresholds, statistical aggregations, telemetry pipelines, or prompts generating such queries.

Judge the signal, not just the code:

- **False positives:** under what conditions does this fire when nothing is wrong (noise, baseline shifts, seasonality)?
- **False negatives:** under what conditions does it stay silent when something is wrong (slow-burn failures, partial failures such as one host out of N)?
- **Statistical soundness:** comparisons are valid (no means without variance, no tiny samples), rate denominators are right, percentiles handle sparse data, windows match data cadence, time buckets align.
- **Actionability:** a fired signal gives the responder enough context to start triage;
  correlated signals do not storm from a single root cause.

Prefer executing the query/rule against representative data when a safe runtime exists;
otherwise label the analysis a hypothesis per the Truth Validation Framework.
Query-language and product specifics (syntax validity, field mappings, scale limits) are domain policy:
load the verified domain overlay for the target repo/org when one applies; do not guess them generically.

## Systemic-Risk Checks (Run When The Diff Crosses Module Or Deploy Boundaries)

Trigger: the diff changes public API contracts, persisted data, cross-module/package imports, or behavior that ships through a staged/rolling rollout.

- **Rolling-deploy coexistence:** old and new code run against the same data/API mid-deploy;
  verify both directions survive the version boundary.
- **Rollout gating:** when the repo's convention or stated intent expects incremental rollout, verify the change is gated the way that convention requires.
  This check verifies expected gating; it never licenses adding unrequested flags (SOP `2.0`).
- **Circular dependencies:** the change does not introduce a dependency cycle between packages/modules.
- **Blast radius:** state what breaks if this change is wrong, and pair each identified risk with a concrete mitigation.

The Deletion-Safety Audit and Replacement/Migration Parity Gate own deletions and replacements;
this section covers the deploy/coupling risk they do not.

## Coverage Checklist (Do Not Skip)

On PR surfaces, first apply the CI Coverage Gate (`pr_common.md`).

A finding-class is exempt only when a present PR CI check genuinely catches it:

- First verify the check exists and covers the class; then CI will flag it — do not re-check or comment on it.
- Do not exempt a class where CI is loosened or absent (e.g. a backport).

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

These four dimensions are the only **canonical** ones: name them exactly; do not rename, merge, or reshape them.

1. **Redundancy** — the change repeats something existing:
   - re-implements an existing helper; re-states a rule already stated elsewhere; adds a path/branch/config that is already present
2. **Verbosity** — the change is bloated beyond the task: extra code/prose, comments that restate code, ceremony, or over-explanation.
3. **Semantic + logical duplication** — two places express the **same meaning or behavior** via different text (not literal copy-paste):
   - parallel branches that should be one; a rule stated two ways; divergent-but-equivalent logic;
     this is the subtle axis literal-clone detectors (`jscpd`) miss
4. **Gaps** — incomplete change:
   - dead code the change stranded; a co-edit-set member left unupdated (doc/diagram/census drift); a half-applied rename;
     a referenced file/symbol that does not exist

For each dimension, anchor any finding in evidence: exact file + location, duplicate's other location, stranded symbol.

Do not assert a hygiene problem you have not pointed at.

## Findings-Set Audit (Run Before Acting On The Finding Set)

Subject: candidate findings and proposed fixes — not the fix diff (Post-Review Stage) or original diff.
Owned by the deciding agent (k-light-review, the direct review modes, or a controller);
in fan-out orchestration this is the findings-auditor's job.

Before fixing, drafting, or presenting findings, run the four dimensions (Post-Review Lens) over the finding set:

- **Redundancy / semantic + logical duplication:** collapse two findings with the same root cause or anchor region into one;
  do not present the same issue twice under different wording.
- **Verbosity:** trim finding text and proposed fixes to the smallest form that still carries the evidence.
- **Gaps:** name any finding asserted without an exact anchor or without a decisive verification path, and either anchor it or drop it.

Also check each surviving finding for **actionability** (is the smallest fix concrete?) and **overengineering** (does the proposed fix exceed the proved problem?).
Merging duplicate findings is a deduplication task, never evidence that the underlying issue is unnecessary; keep the merged candidate.

## Post-Review Stage (Run On Any Change-Producing Flow)

Trigger: a flow has **applied fixes** and mechanical quality gates are green.

Applied-fix flows include:

- local-changes verify-and-fix, PR-fix self-fixes, k-light-review, any pass that edited the working tree

Mechanical quality gates: lint, type_check, tests.

Subject: the **fixes themselves** (the changes the review just made).

1. **Derive the fix diff.**
   - Scope to what this pass changed; use `git diff` for uncommitted fixes, or the commit range / staged set the pass produced when applicable.
   - This fix diff only is the subject; original diff under review is not.
2. **Run the four dimensions** (Post-Review Lens above) over that fix diff: redundancy, verbosity, semantic + logical duplication, gaps.
3. **Resolve in the working tree.**
   - Treat each hygiene finding like any other finding in a verify-and-fix mode.
   - Fix the smallest correct change now: collapse the duplication, trim the verbosity, fill the gap, remove the redundancy.
   - In a read-only context, surface each as a finding with a proposed fix instead of editing.
   - Read-only contexts include reviewing someone else's PR and read-only subagents.
4. **Re-gate if you edited.** If the post-review fixes touched code, re-run lint + type_check + tests before declaring the change done.

This stage closes the loop the mechanical gates leave open: lint/types/tests prove the fixes _work_;
the four dimensions prove the fixes are _clean_.

## Verify-and-Fix Loop (Self-Authored Change-Producing Review)

Shared verify-and-fix spine for self-authored, fix-authorized review surfaces (k-light-review, local-changes mode, or a fix-authorized controller).
Each surface sets its own scope and base-context stance first, then runs this loop.
Read-only lanes do not run this loop's fixes: where a step says fix, they report the precise fix (file, location, smallest change) for the parent to apply.

1. **Build the findings queue.** Walk the whole diff against the Coverage Checklist, ordered by severity (CRITICAL first).
2. **Refute.**
   Run the Candidate Refutation Ladder on each candidate; keep only survivors, record reachability, and drop refuted or unverified findings.
3. **Audit the set.** Run the Findings-Set Audit over the survivors and their proposed fixes before acting.
4. **Fix each finding** (highest severity first): state what is wrong and why in 1-2 lines, verify from evidence (base-context comparison, `/tmp` reproduction, or test run — do not assert without evidence), and apply the smallest correct change.
   For a non-trivial or ambiguous fix, state the options and recommended default, then proceed with the default unless the user intervenes.
   Do not commit or push unless explicitly asked.
5. **Quality gates.** Run the repo's lint + type_check + tests (discover the commands from the repo; do not guess).
   Fix until green or report what remains and why.
6. **Post-Review Stage.**
   Run the Post-Review Stage over the fix diff (the changes this pass made), then re-run the quality gates if the cleanup touched code.
