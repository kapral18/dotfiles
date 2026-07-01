---
name: writing-great-skills
description: "Use when authoring or refactoring a skill (SKILL.md): choosing model- vs user-invocation, writing its frontmatter description/triggers, structuring references, applying leading words, or pruning for predictability. Pairs with cli-skills for CLI-tool skill mechanics."
---

# Writing Great Skills

A skill exists to wrangle determinism out of a stochastic system.
**Predictability** — the agent taking the same _process_ every run, not producing the same output — is the root virtue;
every lever below serves it.

This skill owns the craft of skills.
For CLI-tool skill mechanics (the `tool_version` frontmatter, `--help` verification, source layout), load `~/.agents/skills/cli-skills/SKILL.md`; it owns that surface and the skill source-layout table.
The SOP still owns evidence, minimal edit scope, and the human-visible gates — a skill never restates them.

## Invocation — the one axis that splits every skill

Every `SKILL.md` is either **model-invoked** or **user-invoked**, decided by one field:

- **Model-invoked** (default; omit `disable-model-invocation`) — keeps a `description`, so the agent can fire it autonomously _and_ other skills can reach it (you can still type its name).
  It pays **context load**: the description sits in the window every turn.
  The `description` is model-facing — rich trigger phrasing ("Use when the user wants…, mentions…, asks for…").
- **User-invoked** (`disable-model-invocation: true`) — strips the description from the agent's reach:
  only the human, typing its name, can invoke it, and no other skill can.
  Zero context load, but it spends **cognitive load**: the human is the index that must remember it exists.
  The `description` becomes a human-facing one-liner; strip trigger lists.

Pick model-invocation only when the agent must reach the skill on its own, or another skill must.
If it only ever fires by hand, make it user-invoked and pay no context load.
Because a user-invoked skill has no description, it can invoke model-invoked skills but can never reach another user-invoked one.

The test for staying model-invoked: _could the model usefully reach for this autonomously?_
Reuse alone is not the test — reuse is the reason to extract a skill, not the reason to make it model-invoked.

## Writing the description

A model-invoked `description` does two jobs — state what the skill is, and list the **branches** that should trigger it.
Every word is permanent context load, so it earns harder pruning than the body:

- **Front-load the leading word** — the description is where it does its invocation work.
- **One trigger per branch.**
  Synonyms that rename a single branch are **duplication** — collapse them; keep only genuinely distinct branches.
- **Cut identity already in the body.** Keep the description to triggers plus any "when another skill needs…" reach clause.
- Match this repo's entry contract: put the routing `Use when` in the `description`, since the body only loads after routing.
  Detailed applicability checks may live in the body.

## Information hierarchy

A skill is built from two content types — **steps** (ordered actions the agent performs) and **reference** (definitions, rules, facts consulted on demand) — that mix freely.
Rank each piece by how immediately the agent needs it, on a ladder with three rungs:

1. **In-skill step** — an ordered action in `SKILL.md`, the primary tier. Each step ends on a **completion criterion**.
2. **In-skill reference** — a rule or fact in `SKILL.md`, consulted on demand.
   Often a legitimately flat peer-set (every rule on one rung) — a fine arrangement, not a smell.
3. **External reference** — reference pushed into a separate file under the skill folder, reached by a **context pointer**, loaded only when that pointer fires.

**Progressive disclosure** is the move down the ladder: inline what every **branch** needs, and push behind a pointer what only some branches reach.
Branching is the cleanest disclosure test.
A context pointer's _wording_, not its target, decides when and how reliably the agent reaches the material —
a must-have behind a weak pointer is a variance bug; sharpen the wording before inlining.
Push too little down and the top bloats; push too much and you hide material the agent needs. That tension is the whole decision.

**Co-location** decides what sits beside a piece once placed: keep a concept's definition, rules, and caveats under one heading rather than scattered, so reading one part brings its neighbours.

## Completion criteria

Every step ends on the condition that tells the agent the work is done. Two properties make it a lever:

- **Clarity** — can the agent tell done from not-done?
  A vague bound ("understanding reached") lets attention slip to _being done_ and invites **premature completion**.
- **Demand** — how much it requires. "Every modified file accounted for" forces thorough **legwork** where "produce a change list" does not.
  Demand binds flat reference too ("every rule applied"), which is how a skill with no steps still carries an exhaustiveness bar.

The strongest criteria are both checkable and exhaustive.

## Leading words

A **leading word** (Leitwort) is a compact concept already living in the model's pretraining that the agent thinks with while running the skill (e.g. _tracer bullet_, _fog of war_, _tight loop_, _red_).
Repeated as a token — not restated as a sentence — it accumulates a distributed definition and anchors a whole region of behaviour in the fewest tokens, by recruiting priors the model already holds.

It serves predictability twice: in the body it anchors _execution_ (the agent reaches for the same behaviour every time the word appears);
in the description it anchors _invocation_ (when the same word lives in your prompts, docs, and code, the agent links that shared language to the skill and fires it more reliably).
Reach for an existing pretrained word first — a coined word recruits no priors, so you pay in definition tokens what a pretrained word gives free.

Hunt for restatements a leading word retires: "fast, deterministic, low-overhead" → a _tight_ loop;
"a loop you believe in" → the loop goes _red_ or it doesn't. You win twice: fewer tokens, and a sharper hook.

## Pruning

- **Single source of truth** — keep each meaning in exactly one authoritative place, so changing behaviour is a one-place edit.
- **Relevance** — check every line: does it still bear on what the skill does?
  A line loses relevance by never bearing on the task or by going stale.
- **No-ops** — hunt sentence by sentence: does this line change behaviour versus the model's default?
  A line the model already obeys pays load to say nothing. Delete the whole sentence rather than trim words. Be aggressive.

A weak leading word is a no-op (_be thorough_ when the agent is already thorough-ish);
the fix is a stronger word (_relentless_), not a different technique.

## Failure modes

Use these to diagnose a skill that misbehaves:

- **Premature completion** — ending a step before it is genuinely done, attention slipping to _being done_.
  Defence, in order: sharpen the completion criterion first (cheap, local); only if it is irreducibly fuzzy _and_ you observe the rush, hide the later steps by splitting across a real context boundary (a user-invoked hand-off or a subagent — an inline model-invoked call leaves the later steps in context and clears nothing).
- **Duplication** — the same meaning in more than one place.
  Costs maintenance and tokens, and inflates a meaning's prominence past its real rank. The accidental inverse of a leading word.
- **Sediment** — stale layers that settle because adding feels safe and removing feels risky.
  The default fate of any skill without a pruning discipline.
- **Sprawl** — a skill simply too long, even when every line is live and unique.
  Cure with the hierarchy: disclose reference behind pointers, split by branch or sequence so each path carries only what it needs.
- **No-op** — a line the model already obeys by default. Distinct from irrelevance: a line can be perfectly relevant and still be a no-op.

## When to split

Granularity spends one of the two loads, so split only when the cut earns it:

- **By invocation** — split off a model-invoked skill when you have a distinct leading word that should trigger it, or another skill must reach it.
  You pay context load for the new always-loaded description.
- **By sequence** — split a run of steps when the steps still ahead tempt the agent to rush the one in front of it.
  Hiding them encourages more legwork on the current task.

When user-invoked skills multiply past what you can remember, that piled-up cognitive load is cured by a **router skill**:
one user-invoked skill that names the others and when to reach each.
