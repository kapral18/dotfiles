---
name: improve-codebase
description: Manual-only workflow for proposing one evidence-backed, high-leverage improvement to the current codebase.
disable-model-invocation: true
---

# Improve Codebase

What's the single smartest and most radically innovative and accretive and useful and compelling addition you could make at this point in this codebase?

Only suggest if you think the change is smart, innovative, accretive, useful, and compelling. It's ok to refrain from doing so if you don't have a good suggestion, because no change is sometimes better than a marginally better change.

Use when:

- the user asks `/improve-codebase`
- the user asks for the single smartest, most impactful, or highest-leverage addition to the current repository
- the target is the whole codebase, not only the current diff, branch, PR, or issue

Do not use:

- current local changes only: `~/.agents/skills/improve-local/SKILL.md`
- current branch, PR, or issue only: `~/.agents/skills/improve-branch/SKILL.md`
- broad brainstorming where the user wants many ideas instead of one recommendation

First actions:

1. Inspect the repo shape, documentation, test/validation commands, and current git state.
2. Identify up to three candidate improvements internally, grounded in observed code or docs.
3. Choose exactly one candidate only if it is clearly smart, accretive, useful, and compelling for this repo now.
4. If no candidate clears that bar, say so and do not propose a marginal change.

Selection rules:

- Prefer changes that compound future work: sharper automation, better verification, safer generated config, or clearer agent/tool workflows.
- Scope the recommendation to the real opportunity: small when small is enough, broad when breadth is where the leverage lives.
- Do not recommend package churn, stylistic cleanup, or speculative abstractions unless the repo evidence makes the payoff unusually clear.
- Treat "suggest" literally: present the recommendation first. Do not edit files unless the user explicitly approves implementation.

Output:

- If recommending a change: name the single change, explain why it matters, cite the evidence, and state the expected validation.
- If implementing after approval: keep the edit scoped, update docs when behavior/workflow changes, validate, and report `Compatibility impact: none | removed (requested) | kept existing (requested)`.
- If declining: state that no compelling codebase-wide addition was found and mention the strongest rejected candidate briefly.
