# Judging Core (Surface-Agnostic)

The shared judging engine for every review surface.

- Mode files and the slimmed `shared_rules.md` reference this file.
- Do not duplicate these sections elsewhere.
- This file is delivery-agnostic:
  - no GitHub rules
  - no SCSI rules
  - no delivery rules
- Surfaces that need PR/SCSI/GitHub-delivery rules layer those on top via `shared_rules.md`.

## Truth Validation Framework

Use in every non-trivial review.

- Treat every claim as a hypothesis until verified.
- A static read (reading source, searching the tree) proves what the source says, not what the system does.
  When keeping or dropping a candidate depends on observed/runtime behavior, static evidence is a hypothesis, not proof —
  verify the behavior at runtime whenever a runtime check is available, because a static read can contradict what the system actually does.
  (E.g. a source search indicated no tab tooltips; the live UI rendered four.)
- Establish base invariants first (SCSI when indexed; otherwise `git show <base>:<path>` + local `rg`).
- Validate PR/branch reality second (local diff + file reads).
- When evaluating a proposed change (review suggestion / reviewer request):
  - prefer the smallest reproduction in `/tmp` when possible
  - otherwise run the smallest safe experiment in the worktree
- If you changed code as part of an iteration cycle, re-run the repo's quality gates:
  - lint + type_check + tests (discover the correct commands from the repo; do not guess).
- Keep an evidence log per comment/thread: what base does, what changed, what you tested, and what you observed.

## State-Machine Verification Gate

Use for reviewed behavior that is:

- stateful
- parser-like
- branch-heavy
- dependent on ordered conditions

Examples:

- parsers
- tokenizers
- formatters
- routing/matching logic
- retry/workflow loops
- permission matrices
- compatibility-sensitive branching
- multi-flag control flow

- Before saying the change is final, merge-ready, or a review concern is resolved:
  - build or inspect a disposable harness under `/tmp/state-machine-verification/<pwd>/<topic>/<slug>/`
- The harness must include a `manifest.json` with:
  - worktree path
  - topic
  - slug
  - target files/symbols
  - branch name
  - base/head refs when relevant
  - requested behavior
  - compatibility intent
- Model explicitly:
  - states
  - transitions
  - inputs
  - terminal actions
- Cover:
  - existing behavior buckets
  - requested behavior
  - boundary/malformed inputs
  - regression-sensitive examples
- Compare implementation against an independent model/state table, not just itself.
- When behavior should be preserved:
  - compare against base
  - classify each difference as intended or unexpected
- In review-only PR mode for someone else's work:
  - keep code read-only
  - use the harness to verify claims when safe
  - surface missing or inadequate state-machine coverage as a test gap when risk remains

## Deletion-Safety Audit (Run On Any Removal)

Trigger: the diff deletes:

- files
- exports
- symbols
- behavior

Signals include:

- `git diff --diff-filter=D --stat`
- removed `export`s
- deleted functions/branches

Before calling a deletion safe, verify each item and report a one-line deletion ledger:

- **No live references:** `rg` the deleted symbol/file/path across the repo and public barrels/index files;
  confirm zero live importers/callers.
- **Public surface:** deleted exports are removed from barrels and are not part of a published package entry point still consumed downstream.
- **Behavior parity:**
  - every deleted behavior is intentionally dropped (user-approved per SOP `2.0`) or demonstrably replaced
  - name where each replaced behavior now lives
- **Tests:** deleted tests were migrated, or removed only because the code they covered is gone;
  coverage still exists for behavior that remains after the diff.
- **Base comparison:**
  - for branch-heavy/stateful deletions, compare against base behavior buckets
  - see State-Machine Verification Gate
  - classify each difference as intended or unexpected
- **Disclosure:** meaningful deleted infrastructure is reflected in the PR description (Summary/Fix), not silently dropped.

## Replacement/Migration Parity Gate (Run On Replacements And Test Migrations)

Trigger: the diff deletes or stops using an implementation/test/helper and adds a replacement implementation/test/helper for the same behavior.

Definitions:

- **Old implementation:** the base-branch code/test/helper that the diff deletes, unregisters, or stops calling.
- **Replacement:** the head-branch code/test/helper that now covers the same behavior.
- **Candidate:** a possible review finding before this gate classifies it.

Before a candidate can become review feedback:

1. **Map old to replacement:** identify the old and replacement entry points, helper side effects, assertions/checkpoints, setup/cleanup, permissions, wiring, and runtime assumptions.
   - For every behavior/styling/spacing/layout property the old implementation set explicitly, name where the replacement re-establishes it (which component, prop, or default) or prove it is intentionally dropped.
     "I did not observe a regression" is not evidence the property is preserved;
     absence-of-observation never substitutes for naming the replacement's contract.
   - A migration that hands a property to the target component (e.g. local CSS replaced by a shared component's layout default) is only `preserved_limitation`/`scope_expansion`/intended-replacement once you have pointed at the target's contract that now owns it (static source proof) or verified it live.
     Until then the candidate stays unclassified, not dropped.
2. **Assign exactly one classification:**
   - `parity_gap`: old behavior or coverage existed in the old implementation and is absent or weaker in the replacement.
   - `new_regression`: the replacement introduces a failure mode that the old implementation did not have.
   - `preserved_limitation`: the old implementation had the same limitation and the replacement does not make it worse.
   - `scope_expansion`: the PR body, linked issue, user request, or reviewer request explicitly requires stronger behavior or coverage than the old implementation provided.
   - `prose_drift`: only prose, counts, or docs disagree with the migrated behavior; implementation behavior and coverage remain equivalent.
3. **Keep/drop rule:**
   - Keep `parity_gap`, `new_regression`, and `scope_expansion` as review findings when evidence supports them.
   - Drop `preserved_limitation` from review feedback. Do not ask the author to fix it in this PR.
   - Drop `prose_drift` from code-review feedback.
     If it matters to reviewers, handle it as PR-level prose feedback, not as an implementation finding.
4. **Verification rule:** do not run live UI, heavy runtime probes, or delegated findings audit for `preserved_limitation` or `prose_drift`.
   Run those checks only for a kept candidate when source-level evidence cannot decide whether to keep or drop it.
   - The live-UI skip only applies once step 1's evidence bar is met.
     Never drop a UI-visual candidate (spacing, alignment, layout, visual styling) on an unproven classification and then cite that drop as the reason live UI was unnecessary — that inverts cause and effect.
     If the classification rests on a UI-visual property you have neither traced to the replacement's contract nor verified live, the candidate is unproven: settle it with static proof or live UI before classifying, do not skip the check because the candidate was dropped.

## Historical-Rationale Gate (Deleting/Replacing Long-Lived Infra)

Trigger: removing or replacing:

- custom/legacy stack
- helper that predates current infra
- anything called "obsolete"
- anything called "legacy"
- anything framed as "why does this exist"

Understand the origin before the removal is final.

- **Trace origin:** `git log --follow --oneline -- <path>` and `git blame <base> -- <path>` (or `git log -L` for a function) to find the introducing commit(s).
- **Link intent:** open the offending PR(s)/issue(s) (`gh pr view`, `gh issue view`) to learn the original reason.
- **Classify:** was the behavior being removed (a) the original intended purpose, or (b) drift/side effect that later infra made obsolete?
- **Decide narrative:**
  - if removal corrects historical drift, the PR `## Root Cause` must state:
    - the original reason
    - why it no longer applies
  - if it removes still-needed behavior, stop
  - that is not a safe deletion

## Coverage Checklist (Do Not Skip)

On PR surfaces, first apply the CI Coverage Gate (`pr_common.md`).

A finding-class is exempt only when a present PR CI check genuinely catches it:

- CI will flag it.
- Do not re-check it.
- Do not comment on it.
- First verify the check exists.
- First verify the check covers the class.
- Do not exempt a class where CI is loosened or absent (e.g. a backport).

Non-PR surfaces have no PR CI to dedup against:

- local-changes
- light-review

Check every class below for non-PR surfaces.

- security issues
- logic/correctness/invariants
- data-loss risk
- performance regressions
- test gaps (especially risky changes without tests)
- documentation gaps
- maintainability/complexity
- true nits

## Severity Definitions (Internal Only; Do Not Prefix Comments With These)

- CRITICAL: security vulnerability, data loss/corruption, authz/authn bypass, crash, or unsafe migration.
- HIGH: user-visible bug, broken invariant, serious performance regression, or high operational risk.
- MEDIUM: maintainability risk, unclear behavior, missing tests for a risky change, or non-trivial tech debt.
- LOW: small improvements, clarity, naming/style consistency (true nits).

## Post-Review Lens (The Four Dimensions)

A second-order lens applied to a change set.

Most important subject: the **fix diff** a review just produced (see Post-Review Stage).

These four dimensions are **canonical**:

- name them exactly
- never silently rename them
- never merge them
- never reshape them

1. **Redundancy** — the change repeats something that already exists:
   - re-implements an existing helper
   - re-states a rule already stated elsewhere
   - adds a path/branch/config that is already present
2. **Verbosity** — the change is bloated beyond what the task needs: more code or prose than required, narration comments that restate the code, ceremony, or over-explanation.
3. **Semantic + logical duplication** — two places now express the **same meaning or behavior** via different text (not literal copy-paste):
   - parallel branches that should be one
   - a rule stated two different ways
   - divergent-but-equivalent logic
   - this is the subtle axis literal-clone detectors (`jscpd`) miss
4. **Gaps** — the change is incomplete:
   - dead code the change itself stranded
   - a co-edit-set member left unupdated (doc/diagram/census drift)
   - a half-applied rename
   - a referenced file/symbol that does not exist

For each dimension, anchor any finding in evidence:

- exact file + location
- duplicate's other location
- stranded symbol

Do not assert a hygiene problem you have not pointed at.

## Post-Review Stage (Run On Any Change-Producing Flow)

Trigger: a flow has **applied fixes** and mechanical quality gates are green.

Applied-fix flows include:

- local-changes verify-and-fix
- PR-fix self-fixes
- light-review
- any pass that edited the working tree

Mechanical quality gates:

- lint
- type_check
- tests

This stage is distinct from verifying the original diff.

Subject: the **fixes themselves** (the changes the review just made).

Question: are the review changes well done?

1. **Derive the fix diff.**
   - Scope to what this pass changed.
   - Use `git diff` for uncommitted working-tree fixes.
   - Use the commit range / staged set the pass produced when applicable.
   - This is the subject.
   - The original diff under review is not the subject.
2. **Run the four dimensions** (Post-Review Lens above) over that fix diff: redundancy, verbosity, semantic + logical duplication, gaps.
3. **Resolve in the working tree.**
   - Treat each hygiene finding like any other finding in a verify-and-fix mode.
   - Fix the smallest correct change now:
     - collapse the duplication
     - trim the verbosity
     - fill the gap
     - remove the redundancy
   - In a read-only context, surface each as a finding with a proposed fix instead of editing.
   - Read-only contexts include:
     - reviewing someone else's PR
     - a read-only subagent
4. **Re-gate if you edited.** If the post-review fixes touched code, re-run lint + type_check + tests before declaring the change done.

This stage closes the loop the mechanical gates leave open: lint/types/tests prove the fixes _work_;
the four dimensions prove the fixes are _clean_.
