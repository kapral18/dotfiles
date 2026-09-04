# Findings audit

1. **Run controller findings audit on candidate findings.**
   - Run this phase only after the PR necessity gate, every launched reviewer-lane output (fresh-eyes included when launched), and the live UI result or explicit live-UI skip reason are available.
   - Always audit kept reviewer findings (fresh-eyes clarity candidates included), worker-reported `verification_needed`, live UI evidence/artifacts/blockers or skip reason, and kept PR necessity draft concerns.
     Include only PR necessity concerns kept after the greenlight gate.
   - Maintain a verification ledger for every worker-reported `verification_needed` and every live UI / PR necessity blocker that can affect keep/drop/action.
     The findings audit may recommend dispositions, but it must not erase a ledger item by assuming one branch of an unresolved fork.
   - If two or more reviewer lanes report the same or overlapping root cause, treat that as a merge/deduplication task, not as evidence that the issue is unnecessary.
     Collapse duplicates into one candidate and keep verifying/judging it unless a hard drop rule below is proven.
   - Inline the audit in the controller when the remaining set is trivial:
     - no candidate findings, or
     - one straightforward evidence-backed finding with no lane disagreement, no live UI blocker, no PR-necessity concern kept after greenlight, and no fix diff to audit.
   - Keep the audit in the controller by default; delegate to `k-agent-findings-auditor` only when the remaining set is non-trivial:
     - two or more candidate findings
     - any HIGH/CRITICAL candidate
     - disagreement among reviewer lanes, live UI evidence, or PR necessity concerns, or likely duplication
     - any worker-reported `verification_needed` required to decide whether to keep or drop a candidate
     - any PR necessity concern kept after greenlight
     - live UI comparison/blocker evidence or screenshot handoff needed to decide whether to keep or drop a candidate
     - any named fix diff, staged set, or applied-fix diff
     - any proposed fix that may be overengineered or cross-cutting
   - Audit for:
     - redundancy
     - verbosity
     - semantic + logical duplication
     - gaps
     - actionability of the remaining findings and proposed fixes
     - overengineering risk in proposed fixes
   - This is still investigation, not a decision, even when inlined in the controller.
   - If inlined, still report the audit result in the final output as `Findings audit: inline ...`.
   - For fix-capable own/self-review flows, this pre-action audit does not replace the normal post-review stage over the actual fix diff after fixes are applied.
