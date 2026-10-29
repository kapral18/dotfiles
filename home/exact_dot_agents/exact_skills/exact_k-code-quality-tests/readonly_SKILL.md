---
name: k-code-quality-tests
description: "Use when adding, editing, reviewing, or debugging tests or test plans."
---

# Test Code Quality

Use this for test and verification code. Writing tests does not expand implementation scope.

## Minimum sufficient test protection

New or changed material implementation behavior MUST have durable behavioral test coverage.
Reuse or extend existing tests; add the smallest missing behavioral cases alongside the implementation.
A known bug is not required: new intended behavior needs protection too.
Zero new tests is justified only when existing behavioral coverage is sufficient or there is no material runtime change.
Source inspection, types/static checks and disposable probes help verification but do not replace missing durable behavioral coverage.
Uncovered material behavior is a completion gap.
This floor concerns retained implementation, not prose-only edits or disposable exploration;
apply it before prototype behavior is absorbed into maintained code.
Name the protected outcome or reachable failure, consequence and independent oracle;
branches, fields and coverage percentages are not case quotas.
Do not add tests merely to pin prose/comment wording, trivial wiring, incidental implementation structure or self-authored mock behavior.
Never add a test to justify a helper created only for tests.
In the changed scope, consolidate or remove redundant, superseded or implementation-pinning tests and unused fixtures.
Preserve unique material protection; never remove a failing test to conceal a defect.

## References

- Before choosing which cases to write or judging a suite's coverage, load `~/.agents/skills/k-code-quality-tests/references/case-selection.md`.
- Before writing or reviewing a test body (structure, setup, expectations, test data), load `~/.agents/skills/k-code-quality-tests/references/test-anatomy.md`.
- Before adding or reviewing mocks, stubs, fakes, interaction verification, or tests of non-public code, load `~/.agents/skills/k-code-quality-tests/references/test-doubles.md`.

## Before Writing

- Search for an existing test file for the unit and read it in full; add cases there instead of creating a parallel file.
- Without one, read two or three neighboring test files.
- Reuse the project's assertion library, test-data factories, base fixtures, and setup style.
- Add only missing material protection; no automatic case per branch, boundary, field or error variant.
- Read the types the unit takes, returns, and constructs, so test data uses the real constructors or factories, required fields, and allowed values.

## Test Shape

- Name tests by their condition and observable outcome using the project's framework and naming conventions.
- Extend an existing public-behavior test before creating another test or fixture when that supplies the missing protection.
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
- For artifact-producing changes (suggestion lists, codegen output, definitions, config), verify acceptance against the real consumer's source or contract:
  cite the code or spec that accepts each emitted form (`~/AGENTS.md` §3 step 4).
- For stateful behavior, select transitions that distinguish the concrete material failure and necessary preserved behavior.
  A sequence may share one test; do not enumerate every possible transition.

## Validation

Prepare focused cases with the change; run each planned check once on the finished change.
Use an independent oracle and intended/preserved cases. Do not claim mutation coverage from a green run alone.
Optional mutation experiments for high-risk criteria must establish the control, actual mutation, and restoration, without modifying unrelated work.
Async tests should await the real completion signal rather than arbitrary tick counts. Name the actual worktree/snapshot under test.
Report failed and skipped checks honestly.
Do not add golden files that merely pin wording or generated data against itself.
