# Judging State Gates

Loaded through `~/.agents/skills/k-review/references/judging_core.md` when a listed gate matches the reviewed path, plan claim, or assigned check.
Before using this file directly, load `~/.agents/skills/k-review/references/judging_core.md` for the authoritative triggers.
Apply matching gates in full; loading this group does not activate an unrelated gate.

## State-Machine Verification Gate

For pure input-to-output behavior (parsers, formatters, predicates, matrices), when production tests cannot express the cases the oracle is
a disposable harness under the path `~/.agents/skills/k-formal/SKILL.md` owns (`/tmp/formal-oracle/<pwd>/<topic>/<slug>/`): it loads the
implementation (or a faithful extraction of the predicate) and compares
its outputs against a table the harness computes on its own, with a manifest naming target, requested behavior, compatibility intent, and
snapshot. One harness serves the whole task, never one per worker.
A script that runs the existing tests, or checks that test names appear in a test file, is not a harness.
When the focused tests are the only executable check, report `formal=tests` and write no manifest.

For stateful behavior (lifecycles, retries, ordered/flag-dependent state, permissions over time), the oracle is a `,formal` catalog unit's
audit evidence. The root resolves or builds the unit and runs `,formal audit <unit> --json` once per snapshot in Verify, before assigning a
review lens; a leaf reviewer MUST NOT resolve, build, or audit a unit, and MUST NOT run `,formal audit`/`replay`/`explore`/`mutate` itself.
Read the root-provided `receipts/<snapshot>/audit.json` and cite its `certifies` string. Model results certify the model, not the code;
report conformance (the audit's replay stage) and fidelity (rows vs. code, dispatch/enabledness modeled, hard-coded arguments anchored)
as separate findings. `bounded` search is never reported as an unbounded pass. When no unit or no audit evidence exists for a matching
stateful surface, report a missing-unit gap to the root instead of resolving, building, or auditing one yourself.

In review-only PR mode for someone else's work, the root still keeps the worktree read-only: units live in the catalog, never committed to
the reviewed repo. The root always runs `,formal audit`; only the replay stage inside it is conditional — it runs `replay` only when the
reviewed code runs locally and safely, otherwise `audit.json` reports conformance `unverified`, never pass. A leaf reviewer only ever
reads that evidence.
Surface missing or inadequate state-machine coverage as a test gap when risk remains.

## Async-Derived State Gate (Run On Values Resolved Over Time)

A settled-value-only analysis is incomplete: such values pass through intermediate states (pending, undefined, partial) that production reaches and idealized tests skip.

1. **Value timeline:** enumerate the derived value's states across time — initial evaluation, every transition, final settlement —
   and name every consumer keyed on it: conditionals, dependency arrays, effect re-runs, callback/memo identity, persisted defaults.
   Verify each consumer tolerates each transition, not just each settled state.
   An identity-sensitive consumer (a callback listed in a dependency array) treats a value flip as a new input even when the boolean meaning looks stable.
2. **Transition probe:** a static read cannot clear behavior that depends on such a value _changing_.
   Before a clean verdict on an affected surface, verify the transition by executing or simulating it (disposable test/probe per SOP `3.6`), or report the surface as unverified instead of cleared.
   Green suites do not substitute: tests that set the source to its settled value synchronously never exercise the transition.
3. **Failure vs empty:** for gates fed by fetched collections or remote state, discovery failure and confirmed-empty are distinct inputs;
   a gate mapping both to one outcome silently converts an outage into a valid-empty result.
   Verify the failure path settles differently, or that accepting the merge is explicit.

## Context-Divergence Gate (Run On Shared Paths Serving Multiple Contexts)

A fix verified in one context says nothing about sibling contexts sharing the same code path;
these failures read as successful fixes from inside the reviewed context.

1. **Enumerate sibling contexts:** name every context that reaches the changed path, from scope-level evidence outward (config reads, flag checks, tier/license predicates, role guards).
2. **Classify each context:** preserved, changed, or newly-reachable, anchored against base behavior.
   A context whose behavior flipped silently is HIGH even when the reviewed context's change is correct.
3. **Verify or surface:** exercise at least one intended and one preserved context per SOP `3.5`;
   when a preserved context cannot be verified statically, report it unverified instead of cleared.

## Scale-Behavior Gate (Run On Collection And Volume Operations)

1. **State production n:** name the realistic production scale of the data this operation consumes (items, rows, requests, bytes).
   If unknown, treat as `Unknown` and resolve before clearing.
2. **Trace at boundaries:** walk the operation at 0, 1, typical n, and an order of magnitude beyond;
   check for per-item work moved into loops, queries issued per iteration, unbounded accumulation, and result sets rendered or serialized without a bound.
3. **Report honestly:** a scale hazard here is a finding with severity set by consequence;
   calling the scale safe requires naming the bound, not absence of observation.
