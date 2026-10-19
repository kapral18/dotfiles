---
name: k-improve-codebase
description: "Manual-only: propose one evidence-backed improvement to the current codebase."
disable-model-invocation: true
---

# Improve Codebase

Recommend the improvement with the clearest benefit for its cost.

Use when:

- the user asks `/k-improve-codebase`
- the user asks for the single smartest, most impactful, or highest-leverage addition to the current repository
- the target is the whole codebase, not only the current diff, branch, PR, issue, or a targeted part

Do not use:

- current local changes only: `~/.agents/skills/k-improve-local/SKILL.md`
- current branch, PR, or issue only: `~/.agents/skills/k-improve-branch/SKILL.md`
- targeted part of the codebase: `~/.agents/skills/k-improve-targeted/SKILL.md`
- broad brainstorming where the user wants many ideas instead of one recommendation

First actions:

1. Inspect the repo shape, documentation, test/validation commands, and current git state.
2. Weigh candidate improvements grounded in observed code or docs, and choose exactly one only if it clearly earns its cost for this repo now.
3. If no candidate clears that bar, say so and do not propose a marginal change.

Selection rules:

- Prefer changes that compound future work: sharper automation, better verification, safer generated config, or clearer agent/tool workflows.
- Choose a small or broad change according to its benefit within the requested scope.
- Recommend package churn, stylistic cleanup, or speculative abstractions only when the repo evidence makes the payoff unusually clear.
- Treat "suggest" literally: present the recommendation first. Edit files only after the user explicitly approves implementation.

Output:

- If recommending a change: name the single change, explain why it matters, cite the evidence, name the affected surfaces (consumers and co-edit set), and state the expected validation.
- If implementing after approval: keep the edit scoped, update docs when behavior/workflow changes, validate, and report `Compatibility impact: none | removed (requested) | kept existing (requested)`.
- If declining: state that no compelling codebase-wide addition was found and mention the strongest rejected candidate briefly.
