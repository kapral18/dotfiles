# Judging State Gates

Loaded through `~/.agents/skills/k-review/references/judging_core.md` when a listed gate matches the reviewed path, plan claim, or assigned check.
Before using this file directly, load `~/.agents/skills/k-review/references/judging_core.md` for the authoritative triggers.
Apply matching gates in full; loading this group does not activate an unrelated gate.

## State-Machine Verification Gate

Identify the reachable material failure and necessary preserved behavior in the changed states, ordering or input rules.
Use source/contracts and existing checks first.
If they cannot settle that risk, choose the smallest bounded local probe with an independent oracle;
no automatic harness or case per transition.
Separately ensure minimum sufficient test protection under `~/AGENTS.md` §3; source evidence or a disposable probe does not replace missing durable coverage for new/changed material behavior.
Report the specific unresolved behavior and missing evidence, not a generic coverage gap.

## Async-Derived State Gate (Run On Values Resolved Over Time)

A settled-value-only analysis is incomplete: such values pass through intermediate states (pending, undefined, partial) that production reaches and idealized tests skip.

1. **Value timeline:** enumerate the derived value's states across time — initial evaluation, every transition, final settlement —
   and name every consumer keyed on it: conditionals, dependency arrays, effect re-runs, callback/memo identity, persisted defaults.
   Verify each consumer tolerates each transition, not just each settled state.
   An identity-sensitive consumer (a callback listed in a dependency array) treats a value flip as a new input even when the boolean meaning looks stable.
2. **Transition evidence:** if source/contracts and existing checks cannot settle a concrete material failure caused by the value changing, use the smallest bounded local probe (`~/AGENTS.md` §3 step 4) or report that behavior as unverified.
   A settled-value-only test does not prove a transition; no new probe is required when existing evidence settles it.
3. **Failure vs empty:** for gates fed by fetched collections or remote state, discovery failure and confirmed-empty are distinct inputs;
   a gate mapping both to one outcome silently converts an outage into a valid-empty result.
   Verify the failure path settles differently, or that accepting the merge is explicit.

## Context-Divergence Gate (Run On Shared Paths Serving Multiple Contexts)

1. **Enumerate sibling contexts:** name every context that reaches the changed path, from scope-level evidence outward (config reads, flag checks, tier/license predicates, role guards).
2. **Classify each context:** preserved, changed, or newly-reachable, anchored against base behavior.
   A context whose behavior flipped silently is HIGH even when the reviewed context's change is correct.
3. **Verify or surface:** settle intended and necessary preserved behavior from source/contracts and existing checks.
   Use a bounded local probe only for a concrete material risk that remains unresolved;
   report an unsettled context as unverified instead of cleared.

## Scale-Behavior Gate (Run On Collection And Volume Operations)

1. **Establish bounds:** identify input limits and algorithmic cost from source/contracts, plus expected scale when it affects the conclusion.
   Unknown production volume alone is not a blocker when source bounds settle the risk.
2. **Trace material risks:** check repeated work or queries, unbounded accumulation, and unbounded rendering/serialization.
   Choose boundary inputs only when they distinguish a concrete failure; do not generate a case quota.
3. **Report honestly:** name the bound supporting a safety claim.
   If scale-sensitive behavior remains unsettled, report the specific risk and missing evidence rather than clearing it.
