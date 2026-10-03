# Test Doubles And Test Surface

Seam and port placement belongs to `~/.agents/skills/k-codebase-design/SKILL.md`.

## Enter through the public surface

- Test through the public API the callers use; cover private helpers and internal modules through it.
- Test an internal unit directly only when it is reused across several public entry points, wraps a third-party integration,
  or is complex enough that the root cause would be invisible from the public surface.
- A test that breaks when a helper is renamed or inlined, with behavior unchanged, tests implementation.

## Pick the double

Use the first option that works:

1. The real implementation.
2. A fake the dependency's owners provide (in-memory store, local server).
3. A stub or mock of a wrapper you own around the dependency.

- NEVER mock the unit under test.
- Do not mock plain data (objects, records, structs); construct real ones.
- Do not mock types you do not own. Wrap the third-party type in a thin adapter you own and mock that adapter.

## Assert returned values and state before interactions

- Verify an interaction only when the call is the observable behavior (a state-changing call: send, save, publish, delete),
  or when the collaborator is too slow, nondeterministic, or unavailable to observe its state.
- Do not verify calls to query-only methods (reads, lookups); assert the result they feed instead.
- When verifying a call, pin only the arguments the test is about and match the rest with the framework's wildcard (`expect.anything()`, `ANY`, `any()`).
  Give each other relevant argument its own test.
- For a captured argument object, assert the fields that define the outcome named in the test;
  give independently wrong fields their own tests.

Done when every double is justified by the order above and every interaction verification names a state-changing call.
