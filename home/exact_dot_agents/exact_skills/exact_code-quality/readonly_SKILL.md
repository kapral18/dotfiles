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
- If the change touches React, JSX, TSX, hooks, or component state, also load the `~/.agents/skills/code-quality-react/SKILL.md` skill.
- If the change adds or changes tests, fixtures, mocks, assertions, or test plans, also load the `~/.agents/skills/code-quality-tests/SKILL.md` skill.
- If the change touches HTML, CSS, styles, layout, visual states, accessibility, or browser markup, also load the `~/.agents/skills/code-quality-web/SKILL.md` skill.
- If the change designs a module's interface, decides where a seam goes, or aims to make code more testable, also load the `~/.agents/skills/codebase-design/SKILL.md` skill for the deep-module vocabulary.

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
- Run relevant tests/linters when feasible; report results or state why skipped.
