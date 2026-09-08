# Final Criteria Verification

Use only in the root-owned final Verify stage.
The packet contains the frozen candidate, semantic delta, acceptance criteria, and complete check receipts.
Judge each criterion against the relevant actual artifact and existing evidence. Do not rerun a completed check to establish independence.
Look for intended differences that lack evidence and preserved behavior changed outside the approved scope.
For every criterion, distinguish the claimed outcome from what the check actually observes:

- Criterion truth: a weaker assertion, mock tautology, or expected text from a no-op does not prove the requested behavior.
- Reachability: trace the real user entrypoint to the changed behavior; an isolated helper test does not prove the caller uses it.
- Durability: require applicable evidence that success does not depend on leftover files, caches, seeded state, or a prior attempt.
- Scope accounting: account for every changed path and material behavior against criteria and in/out scope, including generated outputs and compatibility paths.
  An unassigned behavior is a missing criterion or scope violation, not an implicit approval.

Use source and shared receipts to answer these questions; do not invent extra test runs or mutation passes.
When deciding evidence is absent, name the missing observation and affected criterion as unknown;
do not certify reachability or clean-state behavior from a green exit alone.
Return one consolidated result: criterion, supported/unsupported/unknown, exact evidence, and concrete failure if present.
Do not edit, launch another lane, perform a miss-sweep of unrelated scope, or start a repair/convergence loop.
Missing evidence is a failed/blocked condition for the root, not authority for a new workflow.
