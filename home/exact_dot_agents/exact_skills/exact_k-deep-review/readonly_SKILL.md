---
name: k-deep-review
description: "Manual-only deep final review with risk-selected strong specialists and shared evidence."
disable-model-invocation: true
---

# Deep Review

Apply deep coverage inside the SOP's single final Verify stage.
Depth means relevant source, counterexamples, and preserved-behavior analysis, not more workflow layers.
Do not start finder→auditor→refuter→post-review chains or automatically invoke convergence.

## Scope and context

Resolve the requested diff, authorship, base/head, known fixes, and edit/publication authority.
Read `~/.agents/skills/k-review/references/authorship.md`; local checkout does not imply authorship or permission to edit.
For PRs, load `pr_common.md` and `pr_snapshot.md` from the same reference directory for complete intent/context, drift, and pending-review reconciliation.
For other/unknown authorship, gather whether the PR is still needed and correctly open in Understand;
do not create a separate approval/audit ladder. Resolve material intent dependencies from full source artifacts or report uncertainty.
Read `~/.agents/skills/k-deep-review/references/pr-necessity.md` for that conditional intent input and its stopping boundary.
Collect context once; keep raw diffs/discussions in a context pack and concise decisions/pointers in root context.
Read `~/.agents/skills/k-review/references/context-pack.md` when producing/consuming that pack.

## Final review

Freeze the integrated candidate and acceptance plan. Known user-authorized fixes must already be produced and formatted.
Read `~/.agents/skills/k-review/references/judging_core.md` and `judging_pipeline.md` for applicable correctness, severity, and integrated hygiene lenses.
Use existing complete check receipts.
Execute missing planned checks once through direct tools; shared or mutating checks stay root-owned and serialized as needed.
Read `~/.agents/skills/k-deep-review/references/live-ui-validation.md` only when final UI/runtime evidence is needed.
Final reviewers return anchored findings or evidence gaps once.
They do not edit, post, run shared-state mutations, or repeat completed checks.
Merge duplicate causes as output synthesis; do not dispatch an auditor of those findings or another model to verify the verifier.
Final judgment grants no repair authority.
When existing authority covers recovery, the root applies SOP §3.5; this skill MUST NOT create a convergence loop.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Read `~/.agents/skills/k-deep-review/references/reviewer-roster.md` to select the smallest useful strong final roster.
Retain strong artifact review and adversarial challenge as distinct questions in the same final stage, never as reviews of one another.
Select additional specialists only for independent risks; use the blind fresh-eyes contract when comprehension risk warrants it.
Use `~/.agents/skills/k-review/references/runtime-harnesses.md` only for actual invocation/capability caveats.
Workers load leaf contracts and the packet's selected lens, not full controller routers or root memory hooks.
Await each packet once; do not relaunch active/completed packets, poll without new evidence, message siblings, or revive terminal workers.
Record model/effort, stage, packet ID and result pointer in the compact handoff;
do not turn selection metadata into repeated user-facing commentary. Honor no-delegation requests inline.
Report unsupported native lifecycle controls instead of claiming prompt-enforced runtime guarantees.

## Deliver and side effects

Report findings ordered by severity, source/check evidence, base/snapshot identity, unknowns, and relevant UI artifact pointers.
Missing evidence is not a clean verdict. A failed final check is not completion success.
For public-ready text, load `k-communication` and `~/.agents/skills/k-review/references/review_delivery.md`.
Reconcile existing pending review content before drafting/posting.
Keep local screenshot paths out of GitHub bodies; use approved upload mechanics.
No code edits follow final judgment by default; review alone grants no fix authority.
Commit, push, reply, resolve, and publish only under their own explicit/bounded approval and point-of-action checks.
Return compatibility impact when this attempt changed artifacts. Use the root-owned final learning batch; never start a per-worker scribe.
