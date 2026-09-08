---
name: k-code-quality-tests
description: "Use when adding, editing, reviewing, or debugging tests or test plans."
---

# Test Code Quality

Use this for test and verification code. The SOP owns the single final Verify stage; writing tests does not expand implementation scope.

## Test Shape

- Write BDD-style tests when adding tests: `describe('WHEN ...')`, `it('SHOULD ...')`.
- Write regression cases for the reported bug and preserved behavior; execute them in the integrated final Verify stage.
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

## Validation

Prepare focused cases with the change; execute each planned check once in final Verify, not inside production workers.
Use an independent oracle and intended/preserved cases. Do not claim mutation coverage from a green run alone.
Risk-selected final mutation experiments must establish the control, actual mutation, and restoration, without modifying unrelated work.
Async tests should await the real completion signal rather than arbitrary tick counts. Name the actual worktree/snapshot under test.
Report failed/skipped checks honestly; do not automatically repair/recheck.
Do not add golden files that merely pin wording or generated data against itself.
