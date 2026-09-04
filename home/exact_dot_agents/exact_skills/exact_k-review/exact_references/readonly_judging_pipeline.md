# Judging Pipeline (Findings Processing & Post-Review)

- Mode files and `shared_rules.md` reference this file; do not duplicate these sections elsewhere.
- Delivery-agnostic: no GitHub, SCSI, or delivery rules.
- Finding-generation gates, the Candidate Refutation Ladder, and the severity definitions live in `judging_core.md`.

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
   - dead code the change stranded; a co-edit-set member left unupdated (doc/diagram/census drift, or sibling sort/filter/persistence consumer left on old mapping); a half-applied rename; a referenced file/symbol that does not exist

For each dimension, anchor any finding in evidence: exact file + location, duplicate's other location, stranded symbol.

Do not assert a hygiene problem you have not pointed at.

## Findings-Set Audit (Run Before Final Refutation Or Acting)

Subject: candidate findings and proposed fixes — not the fix diff (Post-Review Stage) or original diff.
Owned by the deciding agent (k-light-review, the direct review modes, or a controller).
In deeper fan-out orchestration, keep this in the controller by default and delegate to `k-agent-findings-auditor` only for non-trivial sets.

Before final adversarial refutation, fixing, drafting, or presenting findings, run the four dimensions (Post-Review Lens) over the finding set:

- **Redundancy / semantic + logical duplication:** collapse two findings with the same root cause or anchor region into one;
  do not present the same issue twice under different wording.
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
4. **Re-check if edited.**
   If post-review fixes touched code, re-run the targeted checks for the touched files (focused tests, lint on those files);
   the repo-wide gate runs once per delivery (Verify-and-Fix step 5).
5. **Second pass.** Re-run the four dimensions once after cleanup.
   Hygiene that survives the second pass is reported, not edited again; only a verified blocker or a Requirements Reset ends the stage earlier.

This stage closes the loop: lint/types/tests prove fixes _work_; the four dimensions prove fixes are _clean_.

## Verify-and-Fix Loop (Self-Authored Change-Producing Review)

Shared verify-and-fix spine for self-authored, fix-authorized review surfaces. Each surface sets scope and base-context stance first.
Read-only lanes report precise fixes for the parent to apply instead of editing.

1. **Build the findings queue.** Walk the whole diff against the Coverage Checklist, ordered by severity.
2. **Audit the set.** Run the Findings-Set Audit over candidate findings and proposed fixes.
3. **Final refutation.**
   Run the Candidate Refutation Ladder (`judging_core.md`) or the available `k-agent-adversarial-verifier` lane over the audited set;
   keep only survivors, record reachability, and drop refuted/unverified findings.
4. **Fix each finding** highest severity first: verify from evidence, apply the smallest correct change, and do not commit/push unless asked.
   For non-trivial or ambiguous fixes, state options and proceed with the recommended default unless the user intervenes.
   **Fix scope:** a fix stays inside the behavior the reviewed diff already changes.
   It becomes a proposal, reported with the smallest change and left unapplied, when it needs a new user-visible state (loading, error, retry), a new prop or export on a component outside the diff's package, a file outside the packages the diff touches, or new translated strings beyond the changed component.
   A review that finds a defect it cannot fix inside that scope reports the defect; it does not build the feature.
5. **Targeted checks.** Per fix, run the focused tests and lint for the touched files.
   The repo-wide gate (full suite, type check, check script) runs once, after the last fix and before the report, launched in the background and collected on its completion signal; never block a turn on it and never re-run it per iteration.
6. **Post-Review Stage.** Run it over this pass's fix diff, then re-run the targeted checks if cleanup touched code.
7. **Bound.** One fix round, then one refutation round over the fix diff (Candidate Refutation Ladder or the verifier lane).
   A finding the refuter raises against the fix goes to the user as a decision with the smallest proposed change;
   it is not redesigned in-review.
   After the round, append `round: <n> fixed=<files> gates=<result>` to the review spec and emit a one-line status to the user.
   `k-converge` is the only unbounded loop, and it runs only when the user invokes it.
