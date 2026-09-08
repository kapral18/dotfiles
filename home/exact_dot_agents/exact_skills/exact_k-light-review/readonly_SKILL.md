---
name: k-light-review
description: "Use for one focused final review of low-risk local changes."
---

# Light Review

## Light-Eligibility Predicate

All conditions must hold: local-only diff, verified self-authorship, reversible change, focused observable check, and semantically simple behavior.
Unknown is not eligible.
PR context, explicit full/deep review, security/auth/crypto, persisted data, public API, deletion/replacement, stateful/parser/workflow behavior, or required base/runtime investigation excludes the light path.
Do not treat a small diff or the absence of test failures as low-risk proof.

## Final judgment

Read the requested diff and relevant source; resolve authorship and edit authority without assuming local means self-authored.
Read `~/.agents/skills/k-review/references/judging_core.md` and `~/.agents/skills/k-review/references/judging_pipeline.md`.
This is a final Verify recipe, not a finder/auditor/refuter chain. Judge correctness, preserved behavior, and material completeness once.
Use existing check receipts; do not repeat them.
Return anchored actionable findings, relevant checks and outcomes, or an explicit evidence gap.
This review recipe MUST NOT start post-review or invoke convergence.
A known finding is fixed in the same pass when the caller already holds write scope over the affected path —
the common case for this recipe's own eligibility predicate (verified self-authorship, local-only diff) —
and belongs to Produce before the final review.
When the caller is itself a final-Verify-stage packet, or the path falls outside the caller's granted write scope, this recipe grants no edit authority; the root applies SOP §3.5 when existing authority covers recovery.
Do not commit, push, or publish without explicit authority.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Apply the eligibility predicate before selecting this recipe.
Route ineligible scope to `k-review`, or explicitly requested deep review to `k-deep-review`.
If new risk invalidates eligibility, a leaf returns that scope gap; it MUST NOT load another router or start another review.
Choose one strong review/refute packet when isolation is useful; small bounded review can remain inline.
Do not spawn findings auditors, fresh-eyes workers, or a verifier of that result.

## Output

Findings and evidence, final check outcomes, unresolved conditions, and compatibility impact if this attempt changed artifacts.
