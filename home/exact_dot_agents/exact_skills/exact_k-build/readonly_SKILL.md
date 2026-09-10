---
name: k-build
description: "Manual-only implementation recipe for an approved spec, with one integrated final verification stage."
disable-model-invocation: true
---

# Build

Implement the approved `k-spec` packet through the SOP's Scope → Understand → Produce → Verify → Deliver lifecycle.
This skill supplies build criteria and artifacts; it MUST NOT create another phase graph or verification loop.

## Scope and authority

Read the active packet and its approval. Do not ask again when the user already approved implementation.
Missing material intent goes through `k-spec`; a clear approved request does not need another approval ceremony.
Carry old/new rules, intended and preserved differences, the impact map, owned targets, and final acceptance conditions into the packet.
Approval covers scoped working-tree edits, needed generation/setup, and final checks, not commits, pushes, or publication.
Keep the packet's Out of scope constraints and the SOP ownership, compatibility, and publication gates.

## Produce

Sequence dependencies; independent owned modules may be separate substantial implementation packets.
Create tests and docs with the change, integrate generated outputs, and format before freezing the final candidate.
Update every co-edit-set member named in the impact map in the same change; a consumer left unchanged needs recorded evidence that it is unaffected.
Maintain the compact topic handoff: decisions, dependencies, active/completed packet IDs, artifact pointers, and open criteria.
Use `pending`, `produced`, or `blocked` during production; do not require red/green status from workers.
Do not run acceptance commands, self-review, per-step check runners, or criteria-verifier passes during production.
If a source discovery invalidates the approved approach, return the concrete decision rather than silently changing scope.

## Verify

Freeze the integrated candidate and run the planned checks once, using direct deterministic commands and retained full logs.
Read `~/.agents/skills/k-build/references/criteria-verifier.md` for final criterion judgment over the candidate and those receipts.
Run visual/runtime evidence only for applicable criteria with a verified target; load `k-ui-capture` and the applicable domain overlay then.
Windows coverage remains explicit-only through `k-live-ui-windows`.
Use strong final judgment where needed; retain both artifact review and adversarial challenge for requested deep or high-risk work.
Assign distinct questions against the same candidate and existing evidence, never a chain certifying another review.
Report each criterion as passed, failed, or blocked with evidence. On failure, the root applies SOP §3.5.
This skill MUST NOT create a separate repair, post-review, or convergence loop.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Use the registry's implementation band for substantive edits, with `~/.agents/skills/k-build/references/implement-worker.md`.
Use strong research for substantial unsettled questions and strong review/refute for final judgment; never cheapen judgment work.
Assign criterion judgment to the root or an existing strong final packet using the criteria-verifier contract, not a second verifier of that packet.
Dispatch ready stage-sized packets, not an agent for each command or test. Honor an explicit no-delegation request inline.

## Output

Return the artifact/change summary, criteria results with evidence, remaining failures/decisions, and compatibility impact.
Do not imply that `produced` means verified or that a failed/blocked criterion passed.
Nothing is committed, pushed, or published without its own authority.
