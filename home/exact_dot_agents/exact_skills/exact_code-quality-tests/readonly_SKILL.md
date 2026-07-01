---
name: code-quality-tests
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

## Validation

- Run the smallest relevant test first, then broader checks when the blast radius warrants it.
- If a test cannot be run, state why and what evidence was verified instead.
- Do not add snapshots or golden files unless they protect a meaningful contract.
