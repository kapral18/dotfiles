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

- Run the smallest relevant test first, then broader checks when the blast radius warrants it.
- A passing test proves nothing until it has failed for the right reason.
  Before claiming a test covers a changed observable relation, mutate the code so at least one intended difference fails and, when locally observable, at least one preserved difference fails.
  Confirm both mutations are caught and that unrelated tests do not fail.
- Revert/mutate **in place** from a copy.
  `git stash` on a file whose change is already committed stashes nothing, so the suite passes vacuously and "verified by reverting" is false.
- Waiting for async work: prefer a wait that settles the whole chain (yield a macrotask, or await the real signal) over a fixed number of ticks; a fixed count silently stops reaching the assertion when a step is added, turning every test in the block green-but-vacuous.
- With multiple worktrees/checkouts in play, name the worktree and branch in the run description and confirm the run targets the intended one before interpreting results.
- If a test cannot be run, state why and what evidence was verified instead.
- Add snapshots or golden files only when they protect a meaningful contract.
