# Judging Product Gates

Loaded through `judging_core.md` when a listed gate matches the reviewed path, plan claim, or assigned check.
Before using this file directly, load `~/.agents/skills/k-review/references/judging_core.md` for the authoritative triggers.
Apply matching gates in full; loading this group does not activate an unrelated gate.

## Product-Flow Lens (Run When The Diff Touches User-Facing Flows)

Walk each affected user path as finding generation: trigger -> loading -> result (success or error).

- **Flow completeness:** the user can finish the workflow end-to-end; no path dead-ends without a next action or feedback.
- **Action acknowledgment:** every user-initiated action has loading, success, empty, and error states handled.
- **State consistency:** no stale data after an action, no optimistic update that never reconciles; refresh preserves the expected state.
- **Error experience:** failures produce a meaningful message; the user can recover without losing work;
  transient errors (network, timeout) are distinguishable from permanent ones.
- **Behavior expectations:** no surprises for a user who knows the existing product;
  labels, button text, and placeholders accurately describe what happens; new behavior is discoverable.
- **Data visibility:** the user sees the expected data after an action; pagination, sorting, and filtering stay consistent after the change;
  column sort keys and filter predicates match rendered cell labels and groupings.

These heuristics generate candidates. Verify per Truth Validation Framework; broken user paths are HIGH severity.

## Signal-Quality Gate (Run On Alerting/Monitoring/Analytics Logic)

Judge the signal, not just the code:

- **False positives:** conditions causing firing when nothing is wrong (noise, baseline shifts, seasonality).
- **False negatives:** conditions causing silence when something is wrong (slow-burn, partial/single-node failures).
- **Statistical soundness:** valid comparisons, right rate denominators, sparse percentile handling, aligned time buckets.
- **Actionability:** fired signal gives triage context; correlated signals do not storm from one root cause.

Prefer executing queries against representative data in safe runtimes; otherwise label analysis a hypothesis.
Domain specifics (syntax, mappings, scale limits) come from verified domain overlays.

## Systemic-Risk Checks (Run When The Diff Crosses Module Or Deploy Boundaries)

- **Rolling-deploy coexistence:** old and new code run against the same data/API mid-deploy;
  verify both directions survive version boundaries.
- **Rollout gating:** when conventions expect incremental rollout, verify proper gating (without adding unrequested flags per SOP `2.1`).
- **Circular dependencies:** verify the change does not introduce package/module cycles.
- **Blast radius:** state what breaks if wrong and pair each risk with concrete mitigation.

Deletion-Safety and Parity gates own deletions/replacements; this section covers deploy/coupling risk.
