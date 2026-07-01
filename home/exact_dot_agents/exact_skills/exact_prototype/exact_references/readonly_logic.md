# Logic Prototype

A tiny interactive terminal app that lets the user drive a state model by hand.
Use when the question is about **business logic, state transitions, or data shape** —
the kind that looks reasonable on paper but only feels wrong once pushed through real cases.

Right shape when: "does this state machine handle X then Y", "does this data model let me represent…", "feel out the API before writing it", or anything where the user wants to **press buttons and watch state change**.
If the question is "what should this look like", wrong branch — use `ui.md`.

## Process

### 1. State the question

Before writing code, write down what state model and what question you are prototyping —
one paragraph, in a top-of-file comment or a `NOTES.md`.
A logic prototype that answers the wrong question is pure waste; make the question explicit so it can be checked later.

### 2. Pick the language

Use whatever the host project uses.
Match its existing tooling conventions — do not add a new package manager or runtime just for the prototype.
If the repo has no obvious runtime (e.g. a docs repo), ask.

### 3. Isolate the logic in a portable module

Put the actual logic — the bit answering the question — behind a small, pure interface that could be lifted into the real codebase later.
The TUI around it is throwaway; the logic module is not. Pick the shape that fits the question:

- **A pure reducer** — `(state, action) => state`. Good when actions are discrete events and state is a single value.
- **A state machine** — explicit states and transitions. Good when "which actions are legal right now" is part of the question.
- **A small set of pure functions** over a plain data type. Good when there is no implicit current state.
- **A class/module with a clear method surface** when the logic genuinely owns ongoing internal state.

Keep it pure: no I/O, no terminal code, no `console.log` for control flow.
The TUI imports it and calls in; nothing flows the other direction.
This is what makes the prototype useful past its lifetime — the validated reducer/machine/function set lifts into the real module, the TUI shell gets deleted.

### 4. Build the smallest TUI that exposes the state

A **lightweight TUI**: on every tick, clear the screen and re-render the whole frame, so the user always sees one stable view, not growing scrollback.
Each frame, in order:

1. **Current state**, pretty-printed and diff-friendly (one field per line or formatted JSON). Bold field names, dim less-important context.
   Native ANSI codes are fine (`\x1b[1m` bold, `\x1b[2m` dim, `\x1b[0m` reset).
2. **Keyboard shortcuts** at the bottom: `[a] add [d] delete [t] tick [q] quit`.

Behaviour: initialise a single in-memory state, render the first frame, read one keystroke at a time, dispatch to a handler that mutates state, re-render the full frame (replace, don't append), loop until quit.
The whole frame fits on one screen.

### 5. Make it runnable in one command

Add a script to the project's existing task runner. The user runs `pnpm run <name>` or equivalent — never a remembered path.
If there is no task runner, put the command at the top of the prototype's `NOTES.md`.

### 6. Hand it over

Give the user the run command; they drive it.
The interesting moments are "wait, that shouldn't be possible" — those are bugs in the _idea_, which is the whole point.
Add actions if they ask; prototypes evolve.

### 7. Capture the answer

When it has done its job, the answer is the only thing worth keeping.
Ask what it taught them, or leave a `NOTES.md` so the answer can be filled in before the prototype is deleted.

## Anti-patterns

- **Tests.** A prototype that needs tests is no longer a prototype.
- **Wiring to the real database.** In-memory unless the question is specifically about persistence.
- **Generalising.** No "what if we support X later." It answers one question.
- **Blurring logic and TUI.** If the reducer references `console.log`, prompts, or escape codes, it is no longer portable.
- **Shipping the TUI shell.** The shell is throwaway; the logic module behind it is the bit worth keeping.
