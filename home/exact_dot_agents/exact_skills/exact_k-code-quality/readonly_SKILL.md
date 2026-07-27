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

Do not load secondary skills until read/diff evidence proves the surface is in scope.
When invoked for a broad edit, first identify the concrete changed/read files and choose at most the relevant secondary skill(s).
Do not load React/web/test/design secondaries merely because they might become relevant later.

- Load `~/.agents/skills/k-code-quality-react/SKILL.md` when changed/read files are React, JSX, TSX, hooks, or client-side component state.
- Load `~/.agents/skills/k-code-quality-tests/SKILL.md` when changed/read files are tests, fixtures, mocks, assertions, or test plans.
- Load `~/.agents/skills/k-code-quality-web/SKILL.md` when changed/read files touch browser-rendered HTML, CSS, layout, visual states, accessibility, or focus behavior.
- Load `~/.agents/skills/k-codebase-design/SKILL.md` when the task designs a module interface, decides where a seam goes, or aims to make code more testable.

## Minimal Edit Scope

- Change only what the request requires.
- Preserve all existing behavior outside the explicit scope of the change.
- Do not rewrite surrounding code, remove unrelated behavior, or clean up unrelated lines without explicit approval.
- Dropping unrelated behavior, even if it looks like cleanup, requires explicit user approval.
- Use targeted edits, not full-file rewrites, unless the user asks for a rewrite.
- If a full rewrite is necessary, diff against the original and verify no unrelated behavior was dropped.
- Remove only dead imports, variables, or functions introduced by your changes; mention pre-existing dead code instead of deleting it.
  Every changed line must trace to the request; remove any line that does not.

## Semantic Dedupe And Simplicity

- Remove duplication only after proving it is not a point-of-use guard.
- Check whether each repeated check, instruction, config, or workflow step protects an independently reachable entry point.
- Keep local guards unless every entry path necessarily passes through the shared rule/helper.
- If extracting, route every entry point through the shared helper/reference and verify each one.
- Do not add features, abstractions, flexibility, configurability, or error handling not requested.
- No abstractions for single-use code; no error handling for impossible scenarios.
- If 200 lines would do as 50, rewrite.
- If a senior engineer would call it overcomplicated, simplify.
- Simplicity never licenses dropping behavior or adding unrequested compatibility/legacy paths.

## Artifact Necessity

- Before introducing any new file, config, dependency, service, wrapper, generated artifact, or tool-specific metadata, identify the runtime/tooling consumer.
- Prove the required behavior is missing without it and present with it.
- A "works with it" check is insufficient unless the user explicitly requested that artifact by name.
- If the without-it probe passes, do not add the artifact; if already added, remove it.

## State-Machine Verification

Use this for stateful, parser-like, branch-heavy, ordered, retry/workflow, permission, compatibility-sensitive, or flag-dependent behavior.

Before calling such behavior final or merge-ready, build or inspect a disposable harness under `/tmp/state-machine-verification/<pwd>/<topic>/<slug>/`.

- Include `manifest.json` with worktree, topic, slug, target files/symbols, branch/base/head when relevant, requested behavior, and compatibility intent.
- Reuse an existing harness only after reading its manifest and confirming it still matches.
- Name states, transitions, inputs, terminal actions, existing buckets, requested behavior, boundaries, malformed inputs, and regression-sensitive cases.
- Compare implementation behavior against an independent model/table, not just itself;
  when preserving behavior, compare against base and classify every difference.
- Treat unexpected differences as bugs or true `Unknown`s before finalizing.
- Keep the harness in `/tmp` unless asked to promote compact high-value tests;
  this verifies complexity, not a reason to add production state machines.

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
