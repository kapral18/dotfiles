---
name: k-writing-great-skills
description: "Use when authoring/refactoring skills: invocation, triggers, references, leading words, pruning."
---

# Writing Great Skills

Match specificity to fragility: exact ordered steps where only one sequence is safe (destructive, auth, publication, interactive tooling);
outcomes, constraints, and completion criteria where the work is judgment.

This skill covers skill structure, routing, and pruning.
For CLI-tool mechanics (`tool_version`, `--help`, source layout), load `~/.agents/skills/k-cli-skills/SKILL.md`.
For unambiguous behavioral wording, hard prohibition boundaries, and affirmative reinforcement, load `~/.agents/skills/k-instruction-boundaries/SKILL.md`.
The SOP still owns evidence, minimal edit scope, and human-visible gates; a skill defers to the SOP for those instead of restating them.

## Invocation

Every `SKILL.md` is either model-invoked or user-invoked.

- **Model-invoked** (default; omit `disable-model-invocation`): keep a model-facing routing description for autonomous selection and skill-to-skill use.
- **User-invoked** (`disable-model-invocation: true`): use a human-facing one-line description and require explicit invocation for its workflow unless an applicable caller contract authorizes a scoped handoff.
  Explicit instruction-file loads and authorized handoffs remain possible; loading a file alone grants no workflow or side-effect authority.
  Do not infer context cost or harness discovery behavior from this flag; verify the active loader before making those claims.

Stay model-invoked only when the agent or another skill must reach the skill autonomously.
Reuse is a reason to extract a skill, not a reason to make it model-invoked.

## Description

The `description` is the routing surface: put `Use when` triggers there because the body loads only after routing.
Prune harder than the body.

- Front-load the leading word.
- One trigger per distinct branch; collapse synonyms.
- Cut identity and detailed applicability checks already in the body.
- Keep a “when another skill needs …” reach clause only when real.

## Information hierarchy

Use three rungs:

1. **In-skill step** — ordered action in `SKILL.md`; each step ends with a completion criterion.
2. **In-skill reference** — rule/fact consulted on demand; flat peer-sets are fine.
3. **External reference** — separate file loaded through a context pointer only when that branch needs it.

Progressive disclosure: inline what every branch needs; move branch-only material behind a sharp pointer.
Required guidance needs an explicit load condition; a vague pointer can let an invocation skip it.
Too little disclosure bloats the top; too much hides needed material.
Co-locate each concept's definition, rules, and caveats under one heading.
Do not use bare filenames or relative paths for concrete bundled file references, even when colocated.
Use the full deployed `~/.agents/skills/k-<name>/...` path; use the full chezmoi source path for repo-only files.

## Completion criteria

Every step needs a done condition. Strong criteria are both checkable and exhaustive.

- **Clarity**: can the agent tell done from not-done? Fuzzy criteria invite premature completion.
- **Demand**: “every modified file accounted for” forces legwork; “produce a list” does not.
  Demand also applies to flat reference: “every rule applied.”

## Leading words

Use established domain terms consistently.
Define unfamiliar shorthand, and keep distinct requirements explicit rather than compressing them into one label.

## Pruning

- **Single source of truth**: one meaning, one authoritative place.
- **Relevance**: every line must still bear on the skill; stale or never-used lines go.
- **No-ops**: delete a line only after verifying it changes no required behavior on any reachable invocation.
  Assumed model defaults are not evidence; preserve unique requirements and independently reachable guards.
- **Hard size bound (references)**: keep reference files under 20 KB (`make check` enforces this under `home/exact_dot_agents/`).
  `SKILL.md` is skill-loader delivered and exempt, but nearing the bound is a sprawl signal;
  disclose sections behind pointers or split before squeezing qualifiers.
- **Fossils**: write each rule as if it always existed.
  Drop incident stories, commit hashes, dates, "now / no longer / previous" phrasing, and model names from behavioral text;
  keep the reason as a present-tense mechanism, and keep version pins only as dated verification facts.

Replace vague virtues such as _be thorough_ with concrete completion criteria when they guide behavior;
remove them only when verified redundant.

## Failure modes

- **Premature completion**: the agent ends before done.
  First sharpen the completion criterion; if it is inherently fuzzy and rush is observed, hide later steps across a real context boundary (user-invoked hand-off or subagent, not an inline model-invoked call).
- **Duplication**: one meaning in multiple places; maintenance drift and false prominence.
- **Sediment**: stale layers retained because adding feels safer than removing.
- **Sprawl**: too long even when live and unique; fix with hierarchy, branch disclosure, or sequence split.
- **No-op**: adds no distinct requirement on any reachable invocation, as verified against existing guidance and load paths.

## When to split

Split only for a distinct invocation or workflow stage.

- **By invocation**: split a model-invoked skill only for a distinct leading word that should trigger it, or when another skill must reach it.
- **By sequence**: split steps when seeing later steps tempts the agent to rush the current one.
- If user-invoked skills exceed memory, create a router skill that names them and when to use each.
