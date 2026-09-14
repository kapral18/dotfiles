---
name: k-light-review
description: "Use for one focused final review of low-risk local changes."
---

# Light Review

Subagent dispatch: review — one change-auditor packet.

## Light-Eligibility Predicate

All conditions must hold: local-only diff, verified self-authorship, reversible change, focused observable check, and semantically simple behavior.
Unknown is not eligible.
PR context, explicit full/deep review, security/auth/crypto, persisted data, public API, deletion/replacement, stateful/parser/workflow behavior, or required base/runtime investigation excludes the light path.
Do not treat a small diff or the absence of test failures as low-risk proof.

## Final judgment

The substantive judgment executes in the dispatched change-auditor worker; the root supplies scope and criteria and owns terminal synthesis.
The root resolves the requested diff, authorship and edit authority without assuming local means self-authored.
Read `~/.agents/skills/k-review/references/judging_core.md` and `~/.agents/skills/k-review/references/judging_pipeline.md` to copy the applicable criteria into the packet.
This is a final Verify recipe, not a finder/auditor/refuter chain. The worker judges correctness, preserved behavior, and material completeness once.
Use existing check receipts; do not repeat them.
The worker returns anchored actionable findings, relevant checks and outcomes, or an explicit evidence gap.
This review recipe MUST NOT start post-review or invoke convergence.
Fix authority follows write scope per `~/.agents/skills/k-review/references/authorship.md`; known fixes belong to Produce before the final review.
This recipe grants no edit authority of its own; the root applies SOP §3.5 when existing authority covers recovery.
Do not commit, push, or publish without explicit authority.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Apply the eligibility predicate before selecting this recipe.
Route ineligible scope to `k-review`, or explicitly requested deep review to `k-deep-review`.
If new risk invalidates eligibility, a leaf returns that scope gap; it MUST NOT load another router or start another review.
Launch one strong review subagent using `~/.agents/skills/k-review/references/change-auditor.md` (the `k-agent-change-auditor` profile, or the active harness's generic review-category type carrying that contract where no named profile exists) before any final judgment;
pass the copied applicable criteria from `~/.agents/skills/k-review/references/judging_core.md` and `~/.agents/skills/k-review/references/judging_pipeline.md`, not a router.
The root MUST NOT substitute its own inline review for that packet absent an explicit user no-delegation instruction.
If the required lane or tool is unavailable, report blocked; do not silently fall back to an inline review.
The root still owns scope, scope-level evidence, deterministic checks, integration, and terminal synthesis; the substantive review judgment executes in the worker.
Until the change-auditor packet returns, the root reads only scope-level evidence (`git status`, `git diff --stat`, changed names, `git log --oneline`, check receipts) and MUST NOT read diff hunks, changed-file bodies, callers, or blame output; those reads travel in the packet.
Await the terminal packet result before the verdict; no spawning from a child.
Do not spawn findings auditors, fresh-eyes workers, or a verifier of that result.
See `~/.agents/skills/k-review/references/runtime-harnesses.md` for harness-specific invocation caveats.

## Output

Findings and evidence, final check outcomes, unresolved conditions, and compatibility impact if this attempt changed artifacts.
