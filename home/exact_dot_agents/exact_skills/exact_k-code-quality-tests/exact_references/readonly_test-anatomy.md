# Test Anatomy

## Structure

- Separate arrange, act, and assert. Match the file's existing marker style (`// given/when/then`, `// arrange/act/assert`, or blank lines).
- One act per test.
  Multiple act sections, state changes between assertions, or "and" in the name mean the test holds several scenarios: split it.
- Multiple assertions are fine when they check one behavior: the fields whose failure means the outcome in the name is wrong.
  A field that can be wrong on its own gets its own test; moving it there keeps it asserted, dropping it from every test does not.
- Inside the `WHEN ...` / `SHOULD ...` names, state condition and outcome specifically: `SHOULD return 401` not `SHOULD fail`;
  domain words, not implementation words.
- Prefix result variables `actual...` and expectation variables `expected...` when both sides are named.

## Cause and effect

- Every value the assertion depends on is visible inside the test body.
- Values the assertion does not depend on hide behind a helper.
- Use `beforeEach`/`setUp`/fixtures for infrastructure (servers, doubles, constructing the unit), not for scenario data an assertion relies on.
- Do not share mutable state between tests; each test arranges its own data.

## No logic in tests

- Expected values are literals: `'https://photos.google.com/u/0/photos'`, not `baseUrl + '/u/0/photos'`.
  Concatenation and arithmetic in an expectation can reproduce the bug it should catch.
- No `if`, loops, or try/catch in a test body.
  Use the framework's parametrization (`it.each`, `pytest.mark.parametrize`, table-driven subtests) with literal rows,
  and collection matchers instead of loops over results.
- Prefer clarity over DRY (DAMP): repeat a literal when that keeps the test readable without scrolling.
- When an expectation needs real computation, move it to a helper that has its own tests.

## Test data

- Build data with descriptively named factory helpers that expose only the parameters the scenario varies (`itemWithPrice(10)`, `makeUser({ role: 'admin' })`).
- Switch a helper from positional parameters to named overrides (options object, keyword arguments) when a reader can no longer map positions at a glance.
- Set every value the test depends on explicitly, even when it equals the helper's default; defaults can change underneath the test.
- Keep helpers free of business logic.

## Resilience

- Assert parsed structures or named fields, not serialized strings whose key order or whitespace is incidental.
- Do not depend on iteration order the contract does not guarantee.

Done when each test has one act, its expectations are literals visible in the body, and its name states one condition and one outcome.
