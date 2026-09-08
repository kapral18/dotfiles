---
name: k-text-tournament
description: "Manual-only comparison of materially different prose alternatives against a stated rubric."
disable-model-invocation: true
---

# Text Alternatives

Use only when the user explicitly asks to compare alternatives; ordinary prose edits do not trigger a tournament.
State the goal and preservation constraints, produce distinct useful candidates, and explain the tradeoff.
Do not spawn an evaluator, run two-order judging, create worker SELF_CHECK blocks, or repeat a tournament per edit.
If this is part of a larger task, alternatives belong to Understand/Produce and final assessment belongs to its existing Verify stage.
Instruction safety and factual fidelity remain in force.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Keep comparison inline unless a substantial independent production assignment warrants an isolated context.
Never turn alternative generation into another verification workflow.
