# Final Judging Criteria

The SOP owns the lifecycle. Apply these lenses within the one final Verify stage, not as independent passes.
Use `judging_core.md` for applicable correctness/risk criteria and severity.
PR authorization and delivery remain in their dedicated references.

## Coverage

Select criteria that apply to the actual change: security, correctness/invariants, data loss, performance, test evidence, docs, and maintainability.
Reuse valid CI/local evidence for its actual scope and snapshot; do not rerun checks covered by that evidence.
Do not launch a lane per checklist heading or invent unrelated cleanup findings.

## Integrated hygiene lenses

1. Redundancy — duplicate existing behavior or rules, with both locations named.
2. Verbosity — material scope/reading cost, not stylistic preference.
3. Semantic + logical duplication — equivalent contracts expressed inconsistently across consumers.
4. Gaps — missing affected consumers, docs, generated outputs, tests, or referenced artifacts.

Merge duplicate findings by cause and retain their evidence. Drop unsupported conclusions or mark the missing evidence explicitly.
Actionable findings name the trigger, consequence, anchor, and smallest in-scope correction.
This is output synthesis within final judgment, not a separate Findings-Set Audit or Post-Review Stage.
Final failure goes to Deliver; no automatic repair, second pass, or reviewer-of-reviewer.
