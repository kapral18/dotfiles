# Final Judging Criteria

The SOP owns the lifecycle. Apply these lenses within the one final Verify stage, not as independent passes.
Use `judging_core.md` for applicable correctness/risk criteria and severity.
PR authorization and delivery remain in their dedicated references.

## Coverage

Select criteria that apply to the actual change: security, correctness/invariants, data loss, performance, test evidence, docs, and maintainability.
Reuse valid CI/local evidence for its actual scope and snapshot; do not rerun checks covered by that evidence.
Apply the Check-Coverage Exemption in `judging_core.md` before drafting findings;
local iterate-and-fix review keeps covered classes in scope.
Do not launch a lane per checklist heading or invent unrelated cleanup findings.

## Integrated hygiene lenses

1. Redundancy — duplicate existing behavior or rules, with both locations named.
2. Verbosity — material scope/reading cost, not stylistic preference.
3. Semantic + logical duplication — equivalent contracts expressed inconsistently across consumers.
4. Gaps — missing affected consumers, docs, generated outputs, tests, or referenced artifacts.

Merge duplicate findings by cause and retain their evidence. Drop unsupported conclusions or mark the missing evidence explicitly.
Resolve conflicting conclusions from their underlying source/receipts, not model votes or a second review of the reports.
A material `verification_needed` remains explicit until existing evidence settles it or the missing observation is reported as blocked.
Do not drop uncertainty merely because another finding was removed or the other assigned checks passed.
For blind-clarity findings, explanatory PR narrative is not a refutation; only evidence available to the blind reader can settle the reported confusion.
Actionable findings name the trigger, consequence, anchor, and smallest in-scope correction.
This is output synthesis within final judgment, not a separate Findings-Set Audit or Post-Review Stage.
Report failed criteria faithfully; the root applies SOP §3.5 to determine authorized recovery or delivery of findings and blockers.
No separate repair pass or reviewer-of-reviewer follows.
