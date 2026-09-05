---
name: k-improve-codebase
description: Manual-only workflow for proposing one evidence-backed, high-leverage improvement to the current codebase.
disable-model-invocation: true
---

# Improve Codebase

Propose the single most compelling, high-leverage addition to the current codebase.

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
2. Identify up to three candidate improvements internally, grounded in observed code or docs.
3. Choose exactly one candidate only if it is clearly smart, accretive, useful, and compelling for this repo now.
4. If no candidate clears that bar, say so and do not propose a marginal change.

Selection rules:

- Prefer changes that compound future work: sharper automation, better verification, safer generated config, or clearer agent/tool workflows.
- Scope the recommendation to the real opportunity: small when small is enough, broad when breadth is where the leverage lives.
- Recommend package churn, stylistic cleanup, or speculative abstractions only when the repo evidence makes the payoff unusually clear.
- Treat "suggest" literally: present the recommendation first. Edit files only after the user explicitly approves implementation.

Output:

- If recommending a change: name the single change, explain why it matters, cite the evidence, and state the expected validation.
- If implementing after approval: keep the edit scoped, update docs when behavior/workflow changes, validate, and report `Compatibility impact: none | removed (requested) | kept existing (requested)`.
- If declining: state that no compelling codebase-wide addition was found and mention the strongest rejected candidate briefly.
