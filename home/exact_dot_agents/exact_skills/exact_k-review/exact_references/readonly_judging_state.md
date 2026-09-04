# Judging State Gates

Loaded through `judging_core.md` when a listed gate matches the reviewed path, plan claim, or assigned check.
Before using this file directly, load `~/.agents/skills/k-review/references/judging_core.md` for the authoritative triggers.
Apply matching gates in full; loading this group does not activate an unrelated gate.

## State-Machine Verification Gate

In review-only PR mode for someone else's work, keep the worktree read-only, use the harness to verify claims when safe, and surface missing or inadequate state-machine coverage as a test gap when risk remains.

The harness is an executable independent oracle: it loads the implementation (or a faithful extraction of the predicate) and compares its outputs against a table the harness computes on its own.
A script that runs the existing tests, or checks that test names appear in a test file, is not a harness.
When the focused tests are the only executable check, report `harness=tests` and write no manifest.

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
