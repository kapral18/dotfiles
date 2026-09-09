# PR Fix Batch

Use for an explicit request to address review feedback. Review alone remains read-only.
Resolve PR identity, current head, authorship, and the user-authorized thread set before edits.
Load `~/.agents/skills/k-review/references/pr_common.md` for complete context, pending-review reconciliation, and publication mechanics.
Load `~/.agents/skills/k-review/references/pr_snapshot.md` for head/discussion drift.
Read complete relevant threads and referenced artifacts, not previews.

## Understand

Collect the known batch. For each thread, identify the concern, relevant source/base behavior, reachable consequence, and required decision.
Treat comments as hypotheses; do not implement unsupported suggestions or widen into unrelated cleanup.
Record reply-only, code-change, or ask with evidence. Ask once only for a material user-owned fork.
For explicitly requested one-at-a-time work, the selected thread is the batch; do not silently drain others.

## Produce

Implement the authorized fixes on the implementation band with scoped ownership and intended/preserved differences.
Create regression tests and docs; integrate all fixes and format before final verification.
Workers return produced artifacts, not green checks, findings audits, or per-thread refutation results.
Draft reply intents without claiming unverified outcomes or nonexistent commits.

## Verify and deliver

Run the combined final check plan once for the frozen batch and use strong final judgment where needed.
Do not run per-thread test suites, independent repair loops, or a Post-Review Stage.
Failed criteria block dependent publication; the root applies SOP §3.5 when existing authority covers recovery.
This batch does not create a per-thread repair loop.
Apply Existing Pending Review Reconciliation before public-ready drafts: merge duplicate pending feedback and correct stale content without publishing competing versions.
Load `k-communication` for external wording. Cite actual commit links only after an authorized commit exists.
Return thread decisions, final evidence, unresolved failures, draft replies, and resolve/keep-open recommendations.
For UI feedback retain screenshot handoff paths/descriptions outside GitHub bodies; missing supporting evidence remains explicit.

## Publication authority

Ordinary PR-fix work does not authorize commit/push, replies, or thread resolution.
Apply SOP §3.8: show exact targets/payloads and wait only when existing authorization does not cover the target, payload, and effect.
The explicitly invoked `k-pr-fix-loop` supplies a bounded packet for its scoped sequence; do not ask again within that authority.
Classify authors from platform evidence or a verified domain allowlist, never display names. Ambiguous/mixed authorship is human-supervised.
Verified bot replies/resolves may proceed only inside an explicitly authorized flow;
human replies require supervision or an applicable user-approved bounded packet. Read back authorized writes to confirm they landed.
Transaction readback does not restart quality verification.
Later comments are new input, not a reason to reopen completed workers or run another batch without user authorization.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Keep the compact batch decisions and active/terminal packet IDs in the existing topic.
Dispatch substantial implementation and research, not per-thread audit ladders.
