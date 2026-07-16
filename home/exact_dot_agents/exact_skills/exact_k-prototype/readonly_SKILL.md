---
name: k-prototype
description: "Build a throwaway prototype to answer a design question. Use when the user wants to sanity-check whether a state model or logic feels right, or explore what a UI should look like before committing."
---

# Prototype

A prototype is **throwaway code that answers a question**. The question decides the shape.

The SOP owns minimal edit scope and artifact necessity; a prototype is the explicit exception where throwaway code is the deliverable, so mark it as such and delete or absorb it when done.

## Pick a branch

Identify which question is being answered — from the prompt, the surrounding code, or by asking if the user is around:

- **"Does this logic / state model feel right?"** → load `~/.agents/skills/k-prototype/references/logic.md`.
  Build a tiny interactive terminal app that pushes the state machine through cases hard to reason about on paper.
- **"What should this look like?"** → load `~/.agents/skills/k-prototype/references/ui.md`.
  Generate several radically different UI variations on one route, switchable via a URL search param and a floating bottom bar.

The two branches produce very different artifacts — getting this wrong wastes the whole prototype.
If genuinely ambiguous and the user is unreachable, default to whichever matches the surrounding code (a backend module → logic;
a page/component → UI) and state the assumption at the top of the prototype.

## Rules that apply to both

1. **Throwaway from day one, and clearly marked.**
   Locate it close to where it will be used so context is obvious, but name it so a casual reader sees it is a prototype.
   For throwaway UI routes, obey the project's existing routing convention; do not invent a new top-level structure.
2. **One command to run.**
   Discover the project's existing task runner (`package.json` scripts, `Makefile`, `justfile`, `pyproject.toml`) and add the entry there.
   The user must start it without thinking.
3. **No persistence by default.** State lives in memory — persistence is the thing the prototype is _checking_, not something it depends on.
   If the question is about a database, hit a scratch DB or a local file with a clear "PROTOTYPE — wipe me" name.
4. **Skip the polish.** No tests, no error handling beyond what makes it runnable, no abstractions. Learn something fast, then delete it.
5. **Surface the state.**
   After every action (logic) or on every variant switch (UI), print or render the full relevant state so the user sees what changed.
6. **Delete or absorb when done.** Either delete it or fold the validated decision into the real code — do not leave it rotting in the repo.

## When done

The _answer_ is the only thing worth keeping.
Done when the question, the verdict (keep / discard / refactor), and where the validated decision goes are captured somewhere durable (commit message, PR, issue, `,ai-kb`, or a `NOTES.md` next to the prototype), and the prototype is deleted or scheduled for deletion/absorption.
If the user is around, that capture is a quick conversation; if not, leave the placeholder so the verdict can be filled in before the prototype is deleted.
