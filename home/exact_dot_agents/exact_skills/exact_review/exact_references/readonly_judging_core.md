# Judging Core (Surface-Agnostic)

The shared judging engine for every review surface. Mode files and the slimmed `shared_rules.md` reference this file; do not duplicate these sections elsewhere. This file is delivery-agnostic: it says nothing about GitHub, SCSI, or where findings go. Surfaces that need PR/SCSI/GitHub-delivery rules layer those on top via `shared_rules.md`.

## Truth Validation Framework

Use in every non-trivial review.

- Treat every claim as a hypothesis until verified.
- Establish base invariants first (SCSI when indexed; otherwise `git show <base>:<path>` + local `rg`).
- Validate PR/branch reality second (local diff + file reads).
- When evaluating a proposed change (review suggestion / reviewer request):
  - prefer the smallest reproduction in `/tmp` when possible
  - otherwise run the smallest safe experiment in the worktree
- If you changed code as part of an iteration cycle, re-run the repo's quality gates:
  - lint + type_check + tests (discover the correct commands from the repo; do not guess).
- Keep an evidence log per comment/thread: what base does, what changed, what you tested, and what you observed.

## State-Machine Verification Gate

Use for any reviewed behavior that is stateful, parser-like, branch-heavy, or dependent on ordered conditions: parsers, tokenizers, formatters, routing/matching logic, retry/workflow loops, permission matrices, compatibility-sensitive branching, or multi-flag control flow.

- Before saying the change is final, merge-ready, or a review concern is resolved, build or inspect a disposable harness under `/tmp/state-machine-verification/<pwd>/<topic>/<slug>/`.
- The harness must include a `manifest.json` with worktree path, topic, slug, target files/symbols, branch name, base/head refs when relevant, requested behavior, and compatibility intent.
- Model states, transitions, inputs, and terminal actions explicitly. Cover existing behavior buckets, requested behavior, boundary/malformed inputs, and regression-sensitive examples.
- Compare the implementation against an independent model/state table, not just itself. When behavior should be preserved, compare against base and classify each difference as intended or unexpected.
- In review-only PR mode for someone else's work, keep code read-only; use the harness to verify claims when safe, and surface missing or inadequate state-machine coverage as a test gap when risk remains.

## Deletion-Safety Audit (Run On Any Removal)

Trigger: the diff deletes files, exports, symbols, or behavior (`git diff --diff-filter=D --stat`, removed `export`s, deleted functions/branches). Before calling a deletion safe, verify each and report a one-line deletion ledger:

- **No live references:** `rg` the deleted symbol/file/path across the repo and public barrels/index files; confirm zero live importers/callers.
- **Public surface:** deleted exports are removed from barrels and are not part of a published package entry point still consumed downstream.
- **Behavior parity:** every behavior the deleted code provided is either intentionally dropped (user-approved per SOP `2.0`) or demonstrably replaced — name where each replaced behavior now lives.
- **Tests:** deleted tests were migrated, or removed only because the code they covered is gone; coverage for surviving behavior still exists.
- **Base comparison:** for branch-heavy/stateful deletions, compare against base behavior buckets (see State-Machine Verification Gate) and classify each difference as intended or unexpected.
- **Disclosure:** meaningful deleted infrastructure is reflected in the PR description (Summary/Fix), not silently dropped.

## Historical-Rationale Gate (Deleting/Replacing Long-Lived Infra)

Trigger: removing or replacing a custom/legacy stack, a helper that predates current infra, or anything called "obsolete"/"legacy"/"why does this exist". Understand the origin before the removal is final.

- **Trace origin:** `git log --follow --oneline -- <path>` and `git blame <base> -- <path>` (or `git log -L` for a function) to find the introducing commit(s).
- **Link intent:** open the offending PR(s)/issue(s) (`gh pr view`, `gh issue view`) to learn the original reason.
- **Classify:** was the behavior being removed (a) the original intended purpose, or (b) drift/side effect that later infra made obsolete?
- **Decide narrative:** if removal corrects historical drift, the PR `## Root Cause` must state the original reason and why it no longer applies. If it removes still-needed behavior, stop — that is not a safe deletion.

## Coverage Checklist (Do Not Skip)

On PR surfaces, first apply the CI Coverage Gate (`pr_common.md`): a finding-class a present PR CI check genuinely catches is exempt — CI will flag it, so do not re-check or comment on it. Verify the check exists and covers the class first; do not exempt a class on a branch (e.g. a backport) where CI is loosened or the check is absent. Non-PR surfaces (local-changes, light-review) have no PR CI to dedup against; check every class below.

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

A second-order lens applied to a change set — most importantly to the **fix diff** a review just produced (see Post-Review Stage). These four dimensions are **canonical**: name them exactly, never silently rename, merge, or reshape them.

1. **Redundancy** — the change repeats something that already exists: re-implements an existing helper, re-states a rule already stated elsewhere, or adds a path/branch/config that is already present.
2. **Verbosity** — the change is bloated beyond what the task needs: more code or prose than required, narration comments that restate the code, ceremony, or over-explanation.
3. **Semantic + logical duplication** — two places now express the **same meaning or behavior** via different text (not literal copy-paste): parallel branches that should be one, a rule stated two different ways, or divergent-but-equivalent logic. This is the subtle axis literal-clone detectors (`jscpd`) miss.
4. **Gaps** — the change is incomplete: dead code the change itself stranded, a co-edit-set member left unupdated (doc/diagram/census drift), a half-applied rename, or a referenced file/symbol that does not exist.

For each dimension, anchor any finding in evidence (the exact file + location, the duplicate's other location, the stranded symbol). Do not assert a hygiene problem you have not pointed at.

## Post-Review Stage (Run On Any Change-Producing Flow)

Trigger: a flow has **applied fixes** (local-changes verify-and-fix, PR-fix self-fixes, light-review, or any pass that edited the working tree) and the mechanical quality gates (lint + type_check + tests) are green.

This stage is distinct from verifying the original diff. Its subject is the **fixes themselves** — the changes the review just made — and its question is "are the review changes well done?".

1. **Derive the fix diff.** Scope to what this pass changed: `git diff` (uncommitted working-tree fixes), or the commit range / staged set the pass produced. This is the subject — not the original diff under review.
2. **Run the four dimensions** (Post-Review Lens above) over that fix diff: redundancy, verbosity, semantic + logical duplication, gaps.
3. **Resolve in the working tree.** Treat each hygiene finding like any other finding in a verify-and-fix mode: fix the smallest correct change now (collapse the duplication, trim the verbosity, fill the gap, remove the redundancy). In a read-only context (reviewing someone else's PR, or a read-only subagent), surface each as a finding with a proposed fix instead of editing.
4. **Re-gate if you edited.** If the post-review fixes touched code, re-run lint + type_check + tests before declaring the change done.

This stage closes the loop the mechanical gates leave open: lint/types/tests prove the fixes _work_; the four dimensions prove the fixes are _clean_.
