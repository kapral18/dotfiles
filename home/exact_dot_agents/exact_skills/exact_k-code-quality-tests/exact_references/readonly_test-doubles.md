# Test Doubles And Test Surface

Seam and port placement belongs to `~/.agents/skills/k-codebase-design/SKILL.md`.

## Enter through the public surface

- Test through the public API the callers use; cover private helpers and internal modules through it.
- Test an internal unit directly only when it supplies unique material protection that public entry points cannot express clearly, such as shared logic or third-party adaptation.
- A test that breaks when a helper is renamed or inlined, with behavior unchanged, tests implementation.

## Pick the double

Use the first sufficient option permitted by `~/AGENTS.md` §3 step 4:

1. The real implementation.
2. A fake the dependency's owners provide (in-memory store, local server).
3. A faithful stub or mock of the dependency interface.

- NEVER mock the unit under test.
- Do not mock plain data (objects, records, structs); construct real ones.
- Prefer owner-provided fakes for third-party dependencies.
  Add an owned adapter only when it provides a useful contract or isolates required behavior, not merely to satisfy mock ownership.
- Check a fake or mock against the real dependency's used contract; a self-authored double is not its own oracle.

## Assert returned values and state before interactions

- Verify an interaction only when the call, order, or count is required behavior, or when the collaborator's outcome cannot be observed safely and deterministically.
- For queries, prefer asserting the result; verify the read pattern only when it protects a concrete contract such as avoiding repeated remote calls.
- When verifying a call, pin only the arguments the test is about and match the rest with the framework's wildcard (`expect.anything()`, `ANY`, `any()`).
  Another argument needs a case only when it protects a distinct material failure not covered already.
- For a captured argument object, assert the fields that define the outcome named in the test;
  do not turn each independently wrong field into another test.

Done when every double is justified by the order above and every interaction assertion protects an observable outcome or required call, order, or resource-use contract.
