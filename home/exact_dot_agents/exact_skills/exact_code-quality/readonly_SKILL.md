---
name: code-quality
description: "Use when editing, reviewing, or refactoring implementation code in any language."
---

# Code Quality

Use this for implementation style and maintainability details after the SOP gates are satisfied.
The SOP still owns compatibility, minimal edit scope, artifact necessity, semantic dedupe, verification, and no behavior loss.

## First Actions

- Match local style, structure, terminology, formatting, and contract strength.
- Follow `.editorconfig` and existing project conventions.

## Secondary Skill Escalation

Do not load secondary skills until read/diff evidence proves the surface is in scope.
When invoked for a broad edit, first identify the concrete changed/read files and choose at most the relevant secondary skill(s).
Do not load React/web/test/design secondaries merely because they might become relevant later.

- Load `~/.agents/skills/code-quality-react/SKILL.md` when changed/read files are React, JSX, TSX, hooks, or client-side component state.
- Load `~/.agents/skills/code-quality-tests/SKILL.md` when changed/read files are tests, fixtures, mocks, assertions, or test plans.
- Load `~/.agents/skills/code-quality-web/SKILL.md` when changed/read files touch browser-rendered HTML, CSS, layout, visual states, accessibility, or focus behavior.
- Load `~/.agents/skills/codebase-design/SKILL.md` when the task designs a module interface, decides where a seam goes, or aims to make code more testable.

## General Code Rules

- Avoid TypeScript `as any` and unnecessary type assertions.
- Use `snake_case` for new files unless the project dictates otherwise.
- Use spaced literals: `{ key: 'value' }`, `[ 1, 2, 3 ]`.
- Prefer ESM named imports.
- Replace magic strings with named constants.
- Prefer composition over inheritance; prefer pure functions over side effects.
- Avoid deep nesting; use early returns.
- Keep functions under 50 lines.
- Prefer `async`/`await` over `.then()` chains.
- Add JSDoc/TSDoc for complex functions.
- Treat a behavioral claim in a comment, docstring, or commit message ("safe because", "always", "never", "cannot happen") as a claim to verify against the code and tests, not as evidence; do not preserve or add one you have not confirmed.
- Run relevant tests/linters when feasible; report results or state why skipped.
