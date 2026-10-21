---
name: k-pr-fix-loop
description: "Manual authorized PR-fix batch: scoped fixes, one verification run, then commit, push, and scoped replies."
disable-model-invocation: true
---

# Authorized PR Fix Batch

Use only when the user explicitly invokes this skill or requests the same bounded no-extra-approval sequence.
Invocation authorizes scoped code edits, final verification, commits, a plain (fast-forward) push to the current PR branch, required PR body/media updates, addressed-thread replies, and resolution.
It does not authorize merging, rebasing, pulling/merging base, unrelated metadata, or broad refactors.
A rejected push stops the loop; report it.

1. Resolve the PR URL/number, current head/branch, local changes, and known unresolved thread batch.
2. Use `k-review`'s `~/.agents/skills/k-review/references/pr_fix.md` to understand concerns and produce scoped fixes/tests/docs for that batch.
   Batch scope includes defects in the change's impact (`review_fixes.md` Fix Scope), except one another open thread reports;
   list each in the step 5 report.
3. Run the combined checks once on the finished batch.
   On a failed check or target/branch drift, repair within the batch scope and rerun the affected checks;
   stop after two attempts without progress, on unscoped changes, or on a user-owned decision.
4. Only after passing, use `k-git` to commit scoped files and push the current PR branch without force;
   use `k-github` for required body/media updates and scoped replies/resolves.
5. Read back each authorized write.
   Report commit/PR/reply links, resolved thread IDs, impact-defect fixes, final checks, and remaining external conditions.

Do not ask again for effects inside this authorization. Apply exact-target/payload and ownership/secret checks at the action.
Do not run red/green per thread, create a separate recovery loop, or do a post-publication review.
Do not babysit CI or automatically process later comments; they are new input requiring a new authorized attempt.
