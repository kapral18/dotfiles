---
name: improve-branch
description: Manual-only workflow for proposing one evidence-backed, high-leverage improvement to the current branch, PR, or issue goal.
disable-model-invocation: true
---

# Improve Branch

What's the single smartest and most radically innovative and accretive and useful and compelling addition you could make at this point that would be most beneficial for the goal pursued by current branch and this PR (if it exists) and this issue (that this branch is implementing)?

Only suggest if you think the change is smart, innovative, accretive, useful, and compelling. It's ok to refrain from doing so if you don't have a good suggestion, because no change is sometimes better than a marginally better change.

Use when:

- the user asks `/improve-branch`
- the user asks for the single smartest, most impactful, or highest-leverage addition to the current branch, PR, or issue
- the target is the branch/PR/issue goal, not only the uncommitted local diff or the whole codebase

Do not use:

- whole-codebase improvements: `~/.agents/skills/improve-codebase/SKILL.md`
- current uncommitted/staged diff only: `~/.agents/skills/improve-local/SKILL.md`
- broad brainstorming where the user wants many ideas instead of one recommendation

First actions:

1. Inspect current git status, branch name, branch diff/history, and any discoverable PR or issue context.
2. Identify up to three candidate improvements internally, grounded in the observed branch, PR, or issue goal.
3. Choose exactly one candidate only if it is clearly smart, accretive, useful, and compelling for this branch now.
4. If no candidate clears that bar, say so and do not propose a marginal change.

Selection rules:

- Prefer changes that advance the branch goal: stronger acceptance coverage, cleaner integration, sharper UX/API behavior, clearer migration path, or reduced review risk.
- Scope the recommendation to the real opportunity: small when small is enough, broad when breadth is where the leverage lives.
- Do not recommend unrelated cleanup, package churn, or speculative abstractions unless the branch context makes the payoff unusually clear.
- Treat "suggest" literally: present the recommendation first. Do not edit files unless the user explicitly approves implementation.

Output:

- If recommending a change: name the single change, explain why it matters, cite the branch/PR/issue evidence, and state the expected validation.
- If implementing after approval: keep the edit scoped to the branch goal, update docs when behavior/workflow changes, validate, and report `Compatibility impact: none | removed (requested) | kept existing (requested)`.
- If declining: state that no compelling branch addition was found and mention the strongest rejected candidate briefly.
