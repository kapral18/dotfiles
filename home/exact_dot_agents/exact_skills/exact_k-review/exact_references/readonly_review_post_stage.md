# Review Post-Review Stage

Before using this stage, load `~/.agents/skills/k-review/references/judging_pipeline.md` for the canonical Post-Review Lens.
Read-only role boundaries remain authoritative.

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
