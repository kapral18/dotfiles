---
name: k-code-quality-tests
description: "Use when adding, editing, reviewing, or debugging tests or test plans."
---

# Test Code Quality

Use this for test and verification code.
The SOP still owns required verification loops and the rule that test-first framing does not expand scope.

## Test Shape

- Write BDD-style tests when adding tests: `describe('WHEN ...')`, `it('SHOULD ...')`.
- Bug fix reframe: write a test that reproduces the bug, then make it pass.
- Keep tests focused on observable behavior, not implementation trivia.
- Cover the boundary or regression that would fail without the change.
- Prefer small fixtures that make the behavior obvious.

## Determinism

- Avoid sleeps, real network calls, current-time dependencies, and order-sensitive assertions unless the behavior under test requires them.
- Use local fakes/mocks only where they simplify the observable behavior; do not mock the unit under test into proving itself.
- Make failure output actionable: the assertion should reveal what behavior changed.

## Oracles

- Derive expectations from an oracle independent of the code under test: the consuming system, the upstream spec, or a fixed contract.
- A test that restates generated/spec-derived data as its own expectation only pins current content; it cannot catch invalid content.
  Asserting a suggestion/definition list equals itself proves nothing about whether the suggested values are valid.
- For artifact-producing changes (suggestion lists, codegen output, definitions, config), verify acceptance against the real consumer:
  probe it live when a safe runtime exists, otherwise cite the consumer's contract (spec/source) for every emitted form.

## Validation

- Run the smallest relevant test first, then broader checks when the blast radius warrants it.
- With multiple worktrees/checkouts in play, name the worktree and branch in the run description and confirm the run targets the intended one before interpreting results.
- If a test cannot be run, state why and what evidence was verified instead.
- Do not add snapshots or golden files unless they protect a meaningful contract.
