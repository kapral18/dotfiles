---
name: improve-targeted
description: Manual-only workflow for proposing one evidence-backed, high-leverage improvement to a targeted part of the codebase.
disable-model-invocation: true
---

# Improve Targeted

What's the single smartest and most radically innovative and accretive and useful and compelling addition you could make at this point to a specific targeted part of the codebase (a directory, module, package, feature area, or component)?

Only suggest if you think the change is smart, innovative, accretive, useful, and compelling.
It's ok to refrain from doing so if you don't have a good suggestion, because no change is sometimes better than a marginally better change.

Use when:

- the user asks `/improve-targeted`
- the user asks for the single smartest, most impactful, or highest-leverage addition to a targeted / specific part of the codebase (e.g. "the ralph skill", "the tmux pickers", "@src/components/foo")
- the target is a targeted part of the codebase (scoped dir/module/component), not the whole codebase, not only the current diff, and not the branch/PR/issue goal

Do not use:

- whole-codebase improvements: `~/.agents/skills/improve-codebase/SKILL.md`
- current branch, PR, or issue goal: `~/.agents/skills/improve-branch/SKILL.md`
- current local changes only: `~/.agents/skills/improve-local/SKILL.md`
- broad brainstorming where the user wants many ideas instead of one recommendation

First actions:

1. Identify the targeted scope from the user's request or context (resolve any @path, dir name, or component reference).
2. Inspect the targeted part: its files, structure, tests, docs, and how it integrates with the rest of the repo.
3. Identify up to three candidate improvements internally, grounded in the observed targeted part.
4. Choose exactly one candidate only if it is clearly smart, accretive, useful, and compelling for this targeted part now.
5. If no candidate clears that bar, say so and do not propose a marginal change.

Selection rules:

- Prefer changes that strengthen the targeted part: sharper interfaces/contracts, better encapsulation, stronger targeted tests, clearer invariants, safer error handling, or improved docs specific to it.
- Scope the recommendation to the real opportunity within the target: small when small is enough, broader within the part when that's where leverage lives.
- Do not recommend unrelated cleanup, package churn, or speculative abstractions unless the targeted part's evidence makes the payoff unusually clear.
- Treat "suggest" literally: present the recommendation first. Do not edit files unless the user explicitly approves implementation.

Output:

- If recommending a change: name the single change, explain why it matters, cite the targeted evidence, and state the expected validation.
- If implementing after approval: keep the edit scoped to the targeted part, update docs when behavior/workflow changes, validate, and report `Compatibility impact: none | removed (requested) | kept existing (requested)`.
- If declining: state that no compelling improvement for the targeted part was found and mention the strongest rejected candidate briefly.
