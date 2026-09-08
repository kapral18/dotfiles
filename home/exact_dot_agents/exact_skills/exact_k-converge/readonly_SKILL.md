---
name: k-converge
description: "Manual-only bounded final convergence with an explicit user-approved repair/check allowance."
disable-model-invocation: true
---

# Final Convergence

Use only when the user explicitly requests convergence and specifies or approves a finite repair/check allowance.
Without that allowance, ask one direct question; do not interpret this skill name as unlimited work.
This is an optional mode of the root-owned final Verify stage, not a worker workflow or an automatic handoff.

Freeze scope and retain the current final evidence. Batch correctness findings; refuse wording-only churn and out-of-scope additions.
Within the approved allowance, perform the authorized consolidated repairs and recheck only invalidated acceptance evidence.
Stop when criteria pass, the allowance is exhausted, or a user-owned decision/external blocker remains.
Do not require an extra dry round, repeat unaffected checks, relaunch earlier research, or restart the session lifecycle.
Read `~/.agents/skills/k-converge/references/workflow-handoff.md` for caller authority.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
The root owns the allowance and result.
Strong review/refute judges final artifacts; implementation-band workers produce scoped repairs without private checks.
Do not give any child ownership of convergence or permission to launch another model.

## Output

Final criteria, evidence reused/invalidated, allowance consumed/remaining, and unresolved failures.
Never claim completion from exhaustion alone.
