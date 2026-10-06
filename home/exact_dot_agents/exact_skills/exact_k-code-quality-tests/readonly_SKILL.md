---
name: k-code-quality-tests
description: "Use when adding, editing, reviewing, or debugging tests or test plans."
---

# Test Code Quality

Use this for test and verification code. Writing tests does not expand implementation scope.

## References

- Before choosing which cases to write or judging a suite's coverage, load `~/.agents/skills/k-code-quality-tests/references/case-selection.md`.
- Before writing or reviewing a test body (structure, setup, expectations, test data), load `~/.agents/skills/k-code-quality-tests/references/test-anatomy.md`.
- Before adding or reviewing mocks, stubs, fakes, interaction verification, or tests of non-public code, load `~/.agents/skills/k-code-quality-tests/references/test-doubles.md`.

## Before Writing

- Search for an existing test file for the unit and read it in full; add cases there instead of creating a parallel file.
- Without one, read two or three neighboring test files.
- Reuse the project's assertion library, test-data factories, base fixtures, and setup style.
- Add only behaviors the existing tests do not cover.
- Read the types the unit takes, returns, and constructs, so test data uses the real constructors or factories, required fields, and allowed values.

## Test Shape

- Write BDD-style tests when adding tests: `describe('WHEN ...')`, `it('SHOULD ...')`.
- Write regression cases for the reported bug and preserved behavior; run them with the other checks on the finished change.
- Keep tests focused on observable behavior, not implementation trivia.
- Cover the boundary or regression that would fail without the change.
- Prefer small fixtures that make the behavior obvious.

## Determinism

- Use sleeps, real network calls, current-time dependencies, or order-sensitive assertions only when the behavior under test requires them.
- Use local fakes/mocks only where they simplify the observable behavior; keep the unit under test real so it proves itself against something independent.
- Make failure output actionable: the assertion should reveal what behavior changed.

## Oracles

- Derive expectations from an oracle independent of the code under test: the consuming system, the upstream spec, or a fixed contract.
- A test that restates generated/spec-derived data as its own expectation only pins current content; it cannot catch invalid content.
  Asserting a suggestion/definition list equals itself proves nothing about whether the suggested values are valid.
- For artifact-producing changes (suggestion lists, codegen output, definitions, config), verify acceptance against the real consumer:
  probe it live when a safe runtime exists, otherwise cite the consumer's contract (spec/source) for every emitted form.
- For stateful behavior, list the transitions explicitly (intended, preserved, malformed input, terminal) and test each through an existing seam;
  a pure input-to-output rule can be checked against an independent table in a disposable harness.

## Validation

Prepare focused cases with the change; run each planned check once on the finished change.
Use an independent oracle and intended/preserved cases. Do not claim mutation coverage from a green run alone.
Optional mutation experiments for high-risk criteria must establish the control, actual mutation, and restoration, without modifying unrelated work.
Async tests should await the real completion signal rather than arbitrary tick counts. Name the actual worktree/snapshot under test.
Report failed and skipped checks honestly.
Do not add golden files that merely pin wording or generated data against itself.
