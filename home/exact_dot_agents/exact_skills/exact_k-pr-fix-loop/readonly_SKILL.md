---
name: k-pr-fix-loop
description: Manual no-approval loop for actionable PR review comments through critical assessment, fix, verify, commit, push, PR update, reply, and resolve.
disable-model-invocation: true
---

# PR Fix Loop

Thin manual wrapper around existing PR-fix/review skills.

Use only when the user explicitly invokes this skill or asks for the same no-approval review-comment loop.

Invocation is a bounded approval packet for this loop's normal effects: scoped code edits, verification, commits, force-with-lease push to the current PR branch, PR body updates, needed PR media uploads, review-thread replies, and resolving addressed threads.
Do not ask again for those effects while the target, branch, thread set, and scope stay inside this packet.

It does not authorize merging, rebasing, pulling/merging base, unrelated metadata changes, or broad refactors.

## Load First

- `k-review`, then use `references/pr_fix.md` in Drain Mode.
- `k-code-quality` and `k-code-quality-tests` once code/tests are in scope.
- `k-git` before commit or push.
- `k-github` before PR body edits, replies, uploads, or thread resolution.
- The repo/org domain overlay when the PR target has one.

## Loop

1. Resolve the PR target and latest head.
   Done when the PR URL/number, head SHA, local branch status, and unresolved review threads are read back.

2. Enter `k-review` PR-fix Drain Mode. Follow its per-thread workflow, base-context gate, truth filter, and reply style.
   Do not reimplement those rules here.

3. Start each thread with critical assessment.
   Read the exact new comment body, thread state, affected file/range, current code, and relevant tests. Treat the comment as a hypothesis.
   Keep only findings with a concrete reachable path.

4. Prove before fixing. Prefer a red regression test or minimal local probe that fails for the reviewer’s scenario.
   If the comment is invalid, reply with concise evidence and resolve only when appropriate.

5. Fix narrowly and verify. State compatibility impact before edits. Change only the behavior needed for the validated comment.
   Add or update regression coverage. Run focused checks, then relevant broader checks.

6. Commit and push without another approval prompt. Commit only the scoped files. Match local commit style and required attribution.
   Push the current PR branch with force-with-lease.
   Stop on target mismatch, branch mismatch, unscoped files, failing verification, a rejected push, a conflict that needs a user choice, or an unrelated failure outside PR scope.

7. Update PR body. Add the new fix/test evidence.
   Add screenshot/video pairs only when the new user-visible behavior needs visual proof beyond existing PR media and tests.
   If media is needed, capture/upload it through the GitHub attachment flow before embedding.

8. Reply and resolve without another approval prompt. Reply in-thread with the fix commit link and verification.
   Resolve the thread after read-back confirms the fix landed and the reply posted.

9. Final read-back.
   Report commit SHA, PR URL, reply URL, resolved thread ID, checks run, local status, and any still-pending external checks.

Do not babysit pending CI by default.
If a pending check later creates a new actionable comment or failure, run this loop again for that item.
