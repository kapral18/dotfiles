---
name: k-improve-local
description: "Manual-only: propose one evidence-backed improvement to the local changes."
disable-model-invocation: true
---

# Improve Local

Recommend the improvement with the clearest benefit for its cost.

Use when:

- the user asks `/k-improve-local`
- the user asks for the single smartest, most impactful, or highest-leverage addition to the current local changes
- the target is the uncommitted and/or staged diff, not the whole codebase, a targeted part, or long-running branch goal

Do not use:

- whole-codebase improvements: `~/.agents/skills/k-improve-codebase/SKILL.md`
- current branch, PR, or issue goal: `~/.agents/skills/k-improve-branch/SKILL.md`
- targeted part of the codebase: `~/.agents/skills/k-improve-targeted/SKILL.md`
- broad brainstorming where the user wants many ideas instead of one recommendation

First actions:

1. Inspect current git status and the full staged/unstaged diff.
2. Weigh candidate improvements grounded in the observed local changes, and choose exactly one only if it clearly earns its cost for this local diff now.
3. If no candidate clears that bar, say so and do not propose a marginal change.

Selection rules:

- Prefer changes that strengthen the current diff's purpose, including fewer comments/tests and less scaffolding with material protection preserved; additions must earn their cost.
- Choose a small or broad change according to its benefit within the requested scope.
- Recommend unrelated cleanup, package churn, or speculative abstractions only when the local diff makes the payoff unusually clear.
- Treat "suggest" literally: present the recommendation first. Edit files only after the user explicitly approves implementation.

Output:

- If recommending a change: name the single change, explain why it matters, cite the local evidence, name the affected surfaces (consumers and co-edit set), and state the expected validation.
- If implementing after approval: keep the edit scoped to the local-change goal, update docs when behavior/workflow changes, validate, and report `Compatibility impact: none | removed (requested) | kept existing (requested)`.
- If declining: state that no compelling local-change addition was found and mention the strongest rejected candidate briefly.
