# Test Anatomy

## Structure

- Separate setup, action and result with whitespace; do not add narration comments.
- One material behavior per test.
  Keep a stateful sequence together when the failure depends on its ordering; do not split it just to enforce one act per test.
- Multiple assertions are fine when they check one behavior: the fields whose failure means the outcome in the name is wrong.
  An independently wrong field does not automatically need another test; select assertions by the material contract.
- Inside the `WHEN ...` / `SHOULD ...` names, state condition and outcome specifically: `SHOULD return 401` not `SHOULD fail`;
  domain words, not implementation words.
- Prefix result variables `actual...` and expectation variables `expected...` when both sides are named.

## Cause and effect

- Every value the assertion depends on is visible inside the test body.
- Use `beforeEach`/`setUp`/fixtures for infrastructure (servers, doubles, constructing the unit), not for scenario data an assertion relies on.
- Do not share mutable state between tests; each test arranges its own data.

## No logic in tests

- Expected values are literals: `'https://photos.google.com/u/0/photos'`, not `baseUrl + '/u/0/photos'`.
  Concatenation and arithmetic in an expectation can reproduce the bug it should catch.
- Do not reproduce production logic in a test.
  Short sequences or loops may exercise the public workflow; use parametrization only when it makes necessary cases clearer.
- Prefer clarity over DRY (DAMP): repeat a literal when that keeps the test readable without scrolling.
- Do not create a helper and more tests merely to compute an expectation; choose a simpler independent oracle.

## Test data

- Prefer small literal fixtures; reuse an existing factory when it removes distracting setup. Do not add factories for one-off data.
- Switch a helper from positional parameters to named overrides (options object, keyword arguments) when a reader can no longer map positions at a glance.
- Set every value the test depends on explicitly, even when it equals the helper's default; defaults can change underneath the test.
- Keep helpers free of business logic.

## Resilience

- Assert parsed structures or named fields, not serialized strings whose key order or whitespace is incidental.
- Do not depend on iteration order the contract does not guarantee.

Done when each test protects one material behavior with a clear independent result and no unnecessary cases, comments or scaffolding.
