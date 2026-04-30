---
name: improve-local
description: Manual-only workflow for proposing one evidence-backed, high-leverage improvement to the local changes.
disable-model-invocation: true
---

# Improve Local

What's the single smartest and most radically innovative and accretive and useful and compelling addition you could make at this point to the local changes?

Only suggest if you think the change is smart, innovative, accretive, useful, and compelling. It's ok to refrain from doing so if you don't have a good suggestion, because no change is sometimes better than a marginally better change.

Use when:

- the user asks `/improve-local`
- the user asks for the single smartest, most impactful, or highest-leverage addition to the current local changes
- the target is the uncommitted and/or staged diff, not the whole codebase or long-running branch goal

Do not use:

- whole-codebase improvements: `~/.agents/skills/improve-codebase/SKILL.md`
- current branch, PR, or issue goal: `~/.agents/skills/improve-branch/SKILL.md`
- broad brainstorming where the user wants many ideas instead of one recommendation

First actions:

1. Inspect current git status and the full staged/unstaged diff.
2. Identify up to three candidate improvements internally, grounded in the observed local changes.
3. Choose exactly one candidate only if it is clearly smart, accretive, useful, and compelling for this local diff now.
4. If no candidate clears that bar, say so and do not propose a marginal change.

Selection rules:

- Prefer changes that strengthen the current diff's purpose: sharper validation, clearer behavior, safer edge handling, better docs, or more complete tests.
- Scope the recommendation to the real opportunity: small when small is enough, broad when breadth is where the leverage lives.
- Do not recommend unrelated cleanup, package churn, or speculative abstractions unless the local diff makes the payoff unusually clear.
- Treat "suggest" literally: present the recommendation first. Do not edit files unless the user explicitly approves implementation.

Output:

- If recommending a change: name the single change, explain why it matters, cite the local evidence, and state the expected validation.
- If implementing after approval: keep the edit scoped to the local-change goal, update docs when behavior/workflow changes, validate, and report `Compatibility impact: none | removed (requested) | kept existing (requested)`.
- If declining: state that no compelling local-change addition was found and mention the strongest rejected candidate briefly.
