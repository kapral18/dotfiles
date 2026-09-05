# Adversarial verification

1. **Run final adversarial verification.**
   - If the audited set is empty, skip adversarial verification and report `Adversarial verification: skipped (no candidates after findings audit)`.
   - Otherwise, launch one `k-agent-adversarial-verifier` worker following `~/.agents/skills/k-review/references/adversarial-verifier.md`.
     Give it the audited candidates with lane attribution stripped, plus the findings-audit result, verification ledger, live UI status/evidence/artifacts/skip reason, diff scope, base ref, and mode.
   - Model rule — the one lane where model identity matters: the review-model resolver assigns each harness its verifier model from `category_models.<harness>.refute` or a sparse override, and the deployed `k-agent-adversarial-verifier` profile carries it (named-profile controllers such as Pi/OMP pass the rendered resolver value per task).
     Report `families=cross` only when the resolved verifier model is genuinely a different family than its lane model.
     Report `families=same (reduced independence)` when the resolver carries `verifier_status: reduced_independence` for a deliberate same-family capability-first pairing.
     Report `families=same (degraded)` when the harness cannot field a second family (`verifier_status: degraded`, `inherit`, or single-vendor surface).
     Degradation or reduced independence must be reported, never silent; do not skip the phase because cross-family is unavailable.
   - Verdicts are evidence, not decisions: when recording each `confirmed` / `refuted` / `undecidable (needs <check>)` in the verification ledger, check that a `refuted` verdict's evidence addresses the candidate's actual claim; record it as `undecidable` otherwise.
     "Non-refuted" downstream means not validly refuted after that check.

- The verifier also returns a bounded miss sweep (`new-candidate` items, at most three, or `Miss sweep: none above the bar`).
  These late additions have not passed the findings audit; audit them before judgment.
  Run the `judging_pipeline.md` Findings-Set Audit over them inline, then merge the survivors into the kept set.
  Report how many the sweep produced and how many survived. Do not relaunch the verifier over its own sweep items.
