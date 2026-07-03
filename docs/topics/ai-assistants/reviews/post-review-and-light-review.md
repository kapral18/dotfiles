---
sidebar_position: 3
title: Post-review and light review
---

# Post-review and light review

## Post-review stage (verifying the review's own fixes)

Every change-producing flow ends with a **post-review stage** over the fix diff, not the original diff.

Applies to:

- local-changes verify-and-fix.
- PR-fix self-fixes.
- self-review.
- light-review.

The stage applies the canonical **four dimensions** (defined verbatim in `judging_core.md`, never renamed):

- **Redundancy** — the fix repeats something already present (re-implements a helper, re-states a rule, adds an already-present path).
- **Verbosity** — the fix is bloated beyond what the change needs (narration comments, ceremony, over-explanation).
- **Semantic + logical duplication** — two places now express the same meaning/behavior via different text (parallel branches that should be one; divergent-but-equivalent logic) — the subtle axis literal-clone detectors miss.
- **Gaps** — the fix is incomplete (own stranded dead code, an unupdated co-edit-set member like a doc/diagram/census, a half-applied rename, a referenced-but-missing file).

Post-review behavior:

| Context                   | Behavior                                             |
| ------------------------- | ---------------------------------------------------- |
| own work / self-review    | fix hygiene findings in the working tree and re-gate |
| reviewing others          | surface hygiene findings                             |
| read-only subagent        | surface hygiene findings                             |
| trivial candidate set     | controller audits inline                             |
| non-trivial candidate set | `post-review` / `findings-auditor` runs the lens     |

## Refuting and auditing findings (before acting)

Two engine passes run _before_ fixing or drafting, distinct from the post-review stage that runs _after_:

- **Candidate refutation ladder** — before keeping any finding, the deciding agent tries to kill it in order: claim truth, reachability, severity, proposed fix, already-covered. A candidate survives only when refutation fails with evidence; every kept finding states reachability, and an unreachable path loses its severity. Direct `review`/`light-review` run this as single-model self-refutation; in `/agent-review` the cross-family adversarial lane owns it and read-only finder lanes only return candidates plus reachability.
- **Findings-set audit** — before acting on the survivors, the same four dimensions apply to the _finding list and its proposed fixes_ (not the fix diff): collapse same-root-cause duplicates, trim verbose findings, and drop unanchored, unactionable, or overengineered items. In `/agent-review` this is the `findings-auditor`'s job.

## Light review (proportional depth)

[`light-review`](../../../../home/exact_dot_agents/exact_skills/exact_light-review) is a separate skill for proportional-depth, in-place audits of low-risk self-authored changes.

| Keeps                                                      | Drops                                           |
| ---------------------------------------------------------- | ----------------------------------------------- |
| `judging_core.md` coverage checklist + trigger-based gates | mandatory SCSI/base-context preflight           |
| four-dimension post-review lens                            | GitHub machinery                                |
| candidate refutation ladder + findings-set audit           | multi-agent fan-out + cross-family verification |
| opt-in base context                                        | PR-thread/CI-specific rules                     |

A **light-eligibility predicate** — evaluated first, and the single source both the `review` router and `change-auditor` reference — replaces any subjective "is this low-risk?" call. The change is light-eligible only when none of these escalate: a PR exists for the branch, authorship is not `self` (verified, not assumed from a local checkout), the diff touches security/auth/crypto/secret/migration/persisted-data/public-API paths, it deletes or replaces/migrates code, it is state-machine-like, or correctness needs base context beyond direct local reads. Any trigger escalates to full `review`, and the router applies the same predicate in reverse — offering `light-review` for a self-authored, no-PR, trigger-free diff. `change-auditor` (Claude + Pi) is the read-only delegated form.

Both `light-review` and `review`'s local-changes mode run the shared **Verify-and-Fix Loop** in `judging_core.md` (build queue → refutation ladder → findings-set audit → fix → quality gates → post-review stage); each mode only adds its own base-context stance and scaffolding on top.
