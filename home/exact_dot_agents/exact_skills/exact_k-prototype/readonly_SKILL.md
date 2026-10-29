---
name: k-prototype
description: "Use when building a throwaway prototype to sanity-check logic/state or explore UI direction before committing."
---

# Prototype

A prototype is **throwaway code that answers a question**. The question decides the shape.

`k-code-quality` owns artifact necessity; the core SOP owns minimal edit scope.
`k-prototype` is the point-of-use throwaway exception: mark the prototype as throwaway, then delete or absorb it when done.

## Pick a branch

Identify which question is being answered — from the prompt, the surrounding code, or by asking if the user is around:

- **"Does this logic / state model feel right?"** → load `~/.agents/skills/k-prototype/references/logic.md`.
  Build a tiny interactive terminal app that pushes the state machine through cases hard to reason about on paper.
- **"What should this look like?"** → load `~/.agents/skills/k-prototype/references/ui.md`.
  Generate several radically different UI variations on one route, switchable via a URL search param and a floating bottom bar.

The two branches produce very different artifacts — getting this wrong wastes the whole prototype.
If genuinely ambiguous and the user is unreachable, default to whichever matches the surrounding code (a backend module → logic;
a page/component → UI) and state the assumption in the task record.

## Rules that apply to both

1. **Throwaway from day one, and clearly marked.**
   Locate it close to where it will be used so context is obvious, but name it so a casual reader sees it is a prototype.
   For throwaway UI routes, obey the project's existing routing convention; do not invent a new top-level structure.
2. **One command to run.**
   Discover the project's existing task runner (`package.json` scripts, `Makefile`, `justfile`, `pyproject.toml`) and add the entry there.
   The user must start it without thinking.
3. **No persistence by default.** State lives in memory — persistence is the thing the prototype is _checking_, not something it depends on.
   If the question is about a database, hit a scratch DB or a local file with a clear "PROTOTYPE — wipe me" name.
4. **Skip the polish during disposable exploration.**
   No durable test suite, no error handling beyond what answers the question, no speculative abstractions.
   Learn something fast, then delete it.
5. **Surface the state.**
   After every action (logic) or on every variant switch (UI), print or render the full relevant state so the user sees what changed.
6. **Delete or absorb when done.**
   Delete it or absorb the validated behavior within the authorized implementation scope.
   Absorbed material behavior must meet `~/AGENTS.md` §3's minimum sufficient test protection rule before implementation is complete.

## When done

After the question is answered, record the question, verdict, and destination in the task record, then delete or absorb the prototype.
Do not call its lifecycle complete while cleanup is merely scheduled.
