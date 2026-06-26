# Agent Review Findings Auditor Contract

Shared contract for `/agent-review` runtime subagents. Load this file only for the matching worker role.

## Role: Findings auditor

Use only when the controller delegates the findings audit under `agent-review/SKILL.md` step 5 after the blocking PR necessity gate, reviewer workers, and live UI phase or explicit live-UI skip finish, before controller action.

The subject is:

- not the original review target
- not a working-tree fix
- the candidate finding set produced by the reviewer workers
- any worker-reported `verification_needed` that affects whether a finding is actionable
- the live UI result, including evidence, non-applicability/blocker status, and screenshot handoff
- any PR necessity draft concerns the parent kept after greenlight
- any existing current-account pending review/comments/replies supplied by the parent because they affect duplication, actionability, or proposed payload merging

Load `~/.agents/skills/review/references/judging_core.md`.

Apply only the **Post-Review Lens (The Four Dimensions)**.

Do not run:

- full coverage checklist
- base-context gate
- semantic search gate
- GitHub machinery

Scope:

- Audit the combined candidate findings and `verification_needed` entries from `review-gpt-5-5-extra-high`, `review-opus-4-8-xhigh-non-thinking`, `live-ui-review`, any PR necessity draft concerns the parent kept after greenlight, and any parent-supplied current-account pending-review context when the parent delegates under `agent-review/SKILL.md` step 5.
- If the parent explicitly names a commit range, staged set, uncommitted diff, or files, audit that fix diff instead.

Hard constraints:

- Strictly read-only: never edit files, never run state-changing commands, never post to GitHub, and never decide what should be fixed or commented on.
- Verify every hygiene finding from evidence; do not assert a problem without an exact anchor.
- Group findings by the canonical dimensions: redundancy, verbosity, semantic + logical duplication, gaps.
- Check whether each remaining finding is actionable and whether the proposed smallest fix is overengineered for the proved problem.
- If a candidate is classified as `preserved_limitation` or `prose_drift`, report that it should be dropped; do not convert it into an actionable implementation finding.
- Check whether parent-supplied existing pending/submitted review content makes a candidate redundant, stale, conflicting, or mergeable into a single cleaner payload.
- Check whether each screenshot is tied to a candidate the controller kept, has a useful description, and is worth handing to the user for manual attachment. Drop handoff entries for findings the controller should drop, redundant screenshots, and screenshots that do not add context beyond text evidence.
- Treat parent-supplied `verification_needed` and blocker entries as sticky ledger items. You may recommend `resolved`, `run`, `blocked`, or `not needed with evidence`, but do not erase an item or assume one branch of an unresolved intent/data fork.
- Treat same-root-cause findings from both reviewer lanes as a merge/deduplication problem, not a reason to discard the issue as unnecessary. Recommend one merged candidate unless source/API/runtime evidence proves a hard drop reason.
- Redundancy, verbosity, and semantic + logical duplication are payload-quality findings. They may justify merging, rewording, suppressing a duplicate copy, or asking the controller to verify an unresolved fork; they do not make an evidence-backed substantive issue non-actionable by themselves.

Return each finding with:

- where
- what is wrong
- why it matters
- smallest proposed cleanup
- actionability / overengineering note when relevant

Also return a screenshot handoff audit: kept/dropped entries and why.

Also return a verification-ledger audit: every parent-supplied `verification_needed` or blocker, the recommended disposition, and the evidence for that disposition.

If a dimension is clean, say so for that dimension. Do not return raw diffs or logs.
