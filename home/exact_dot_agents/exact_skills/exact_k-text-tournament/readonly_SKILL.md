---
name: k-text-tournament
description: "Manual-only comparison of materially different prose alternatives against a stated rubric."
disable-model-invocation: true
---

# Text Alternatives

Subagent dispatch: inline (implement for a substantial independent production assignment) — comparison stays inline.

Use only when the user explicitly asks to compare alternatives; ordinary prose edits do not trigger a tournament.
State the goal and preservation constraints, produce distinct useful candidates, and explain the tradeoff.
Do not spawn an evaluator, run two-order judging, create worker SELF_CHECK blocks, or repeat a tournament per edit.
If this is part of a larger task, alternatives belong to Understand/Produce and final assessment belongs to its existing Verify stage.
Instruction safety and factual fidelity remain in force.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Keep comparison inline.
Launch one implement packet only for a substantial independent production assignment with settled constraints;
the root MUST NOT substitute its own inline production for that packet absent an explicit user no-delegation instruction;
if the lane is unavailable report blocked.
Never turn alternative generation into another verification workflow.
