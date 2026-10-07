# Mode: PR Fix

Use for an explicit request to address review feedback. Review alone stays read-only.
Resolve PR identity, current head, authorship (`~/.agents/skills/k-review/references/authorship.md`), and the set of threads the user authorized before any edit.

## Understand the batch

Load `~/.agents/skills/k-review/references/pr_common.md` (GitHub Context Intake + Reference Resolution) and `~/.agents/skills/k-review/references/pr_snapshot.md` (head and discussion drift) once.
Read complete threads and referenced artifacts, not previews.

For each thread, identify the concern, the relevant source and base behavior, the reachable consequence, and the decision:
reply only, code change, or ask.
Treat reviewer comments as hypotheses; do not implement unsupported suggestions or widen into cleanup.
Ask once only for a decision that is genuinely the user's.
For one-at-a-time work, the selected thread is the batch; do not silently drain the others.

## Fix and verify

1. Implement the authorized fixes inside `~/.agents/skills/k-review/references/review_fixes.md` Fix Scope, with regression tests and docs.
2. Run the combined checks once on the finished batch. No per-thread test runs.
3. Re-read the fix diff once against each thread's concern.
   Do not start another review round, except the `~/AGENTS.md` §3 steps 5–6 review that a risky fix needs.
4. Apply Existing Pending Review Reconciliation (`pr_common.md`) before drafting replies.
5. Load `k-communication` for reply wording. Cite commit links only after an authorized commit exists; never claim an unverified outcome.

Return: per-thread decision, check results, unresolved failures, draft replies, and resolve or keep-open recommendations.
Keep UI screenshot paths outside GitHub bodies.

## Publication

PR-fix work does not authorize commit, push, replies, or thread resolution.
Show exact targets and payloads and wait, unless existing approval covers that exact effect (`~/AGENTS.md` §5).
The user-invoked `k-pr-fix-loop` approves its own scoped sequence; do not ask again inside it.
Classify authors from platform evidence (`user.type == "Bot"`, a login ending `[bot]`, or a verified domain allowlist), never display names.
Mixed or ambiguous authorship stays human-supervised. Read back every authorized write to confirm it landed.
Comments that arrive later are new input, not a reason to rerun the batch without the user's request.
