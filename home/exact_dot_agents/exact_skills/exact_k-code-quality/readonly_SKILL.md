---
name: k-code-quality
description: "Use when editing, reviewing, or refactoring implementation code or any repository artifact."
---

# Code Quality

Use this for repository artifact quality: implementation style, maintainability, minimal edit scope, semantic dedupe, and artifact necessity.
The core SOP still owns compatibility and verification; this skill owns the code-quality contract at the point of use.

## First Actions

- Match local style, structure, terminology, formatting, and contract strength.
- Follow `.editorconfig` and existing project conventions.

## Secondary Skill Escalation

Load secondary skills only after read/diff evidence proves the surface is in scope.
When invoked for a broad edit, first identify the concrete changed/read files and choose at most the relevant secondary skill(s).
Load React/web/test/design secondaries only for surfaces the evidence already puts in scope, never because they might become relevant later.

- Load `~/.agents/skills/k-code-quality-react/SKILL.md` when changed/read files are React, JSX, TSX, hooks, or client-side component state.
- Load `~/.agents/skills/k-code-quality-tests/SKILL.md` when changed/read files are tests, fixtures, mocks, assertions, or test plans.
- Load `~/.agents/skills/k-code-quality-web/SKILL.md` when changed/read files touch browser-rendered HTML, CSS, layout, visual states, accessibility, or focus behavior.
- Load `~/.agents/skills/k-codebase-design/SKILL.md` when the task designs a module interface, decides where a seam goes, or aims to make code more testable.

## Minimal Edit Scope

- Change only what the request requires.
- Preserve all existing behavior outside the explicit scope of the change.
- Leave surrounding code, unrelated behavior, and unrelated lines as they are; rewriting or cleaning them up requires explicit approval.
- Dropping unrelated behavior, even if it looks like cleanup, requires explicit user approval.
- Use targeted edits, not full-file rewrites, unless the user asks for a rewrite.
- If a full rewrite is necessary, diff against the original and verify no unrelated behavior was dropped.
- Remove only dead imports, variables, or functions introduced by your changes; mention pre-existing dead code instead of deleting it.
  Every changed line must trace to the request; remove any line that does not.
- When changing how a domain concept, state, or enum is mapped or partitioned, updating co-located sibling consumers (comparators, filters, search predicates, serializers) is required to preserve projection symmetry and traces to the change.

## Semantic Dedupe And Simplicity

- Remove duplication only after proving it is not a point-of-use guard.
- Check whether each repeated check, instruction, config, or workflow step protects an independently reachable entry point.
- Keep local guards unless every entry path necessarily passes through the shared rule/helper.
- If extracting, route every entry point through the shared helper/reference and verify each one.
- Add only the features, abstractions, flexibility, configurability, and error handling the request asks for.
- No abstractions for single-use code; no error handling for impossible scenarios.
- If 200 lines would do as 50, rewrite.
- If a senior engineer would call it overcomplicated, simplify.
- Simplicity never licenses dropping behavior or adding unrequested compatibility/legacy paths.

## Artifact Necessity

- Before introducing any new file, config, dependency, service, wrapper, generated artifact, or tool-specific metadata, identify the runtime/tooling consumer.
- Prove the required behavior is missing without it and present with it.
- A "works with it" check is insufficient unless the user explicitly requested that artifact by name.
- If the without-it probe passes, leave the artifact out; if already added, remove it.

## General Code Rules

- Use precise TypeScript types; `as any` and unnecessary type assertions hide real type errors.
- Use `snake_case` for new files unless the project dictates otherwise.
- Use spaced literals: `{ key: 'value' }`, `[ 1, 2, 3 ]`.
- Prefer ESM named imports.
- Replace magic strings with named constants.
- Prefer composition over inheritance; prefer pure functions over side effects.
- Keep nesting shallow; use early returns.
- Keep functions under 50 lines.
- Prefer `async`/`await` over `.then()` chains.
- Add JSDoc/TSDoc for complex functions.
- Treat a behavioral claim in a comment, docstring, or commit message ("safe because", "always", "never", "cannot happen") as a claim to verify against the code and tests, not as evidence; preserve or add one only after you have confirmed it.
- Run relevant tests/linters when feasible; report results or state why skipped.
