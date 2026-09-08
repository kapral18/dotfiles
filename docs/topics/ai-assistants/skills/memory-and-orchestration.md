---
sidebar_position: 3
title: Memory and orchestration
---

# Memory and orchestration

These skills supply mechanics within the root-owned lifecycle, durable learning, and user-intent discovery. They do not own nested orchestration stages.

## `k-ai-kb`

| Field    | Value                                                                            |
| -------- | -------------------------------------------------------------------------------- |
| Use when | recalling or persisting durable cross-session knowledge via `,ai-kb`             |
| Source   | [`exact_k-ai-kb`](../../../../home/exact_dot_agents/exact_skills/exact_k-ai-kb/) |
| Related  | [Agent memory](../knowledge-base/index.md)                                       |

Automatic hooks retrieve and stage relevant capsules; the root owns admission and one final verified learning batch. Preserve relevance/workspace filters and admitted-ID deduplication. Do not add a recall or scribe invocation per skill, correction or worker. When delegation is forbidden, the same search-first, evidence-backed write/readback mechanics run inline without another model.

## `k-proof`

| Field    | Value                                                                                                                                                                            |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Use when | an explicit proof-ledger/receipt request, auditable security/auth/data-migration/destructive effect, or named handoff/resume consumer needs a durable freeform receipt           |
| Source   | [`exact_k-proof`](../../../../home/exact_dot_agents/exact_skills/exact_k-proof/)                                                                                                 |
| CLI      | `,proof` stores proof state outside worktrees under `$AGENT_PROOF_HOME`, `$XDG_STATE_HOME`, or `~/.local/state`; reports require a finalized ledger with an intact seal          |
| Boundary | runtime/UI/external checks, multi-file scope, failed commands, and late completion challenges use inline evidence unless one of the receipt triggers above independently applies |

`k-proof` is available in two ways. Explicit receipt requests route through the skill frontmatter and `SKILL.md`. Non-review/non-build iteration gets the same narrow receipt gate from the always-on SOP and the shared verification prefix that `perturn_recall.py` re-injects after material context growth or a compaction. The ledger is a durable receipt, not verification itself: evidence collection remains mandatory and inline by default. When a receipt trigger applies, choose the topic and criteria before ledger-bound evidence collection, finalize the ledger, and only then generate a report.

| Field   | Value                                                                                                                            |
| ------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Routing | model-invoked only after that explicit user intent; ordinary task size, complexity, or instructions to continue never trigger it |

## `k-interview-me`

| Field    | Value                                                                                          |
| -------- | ---------------------------------------------------------------------------------------------- |
| Use when | reverse-interviewing the user until intent is fully clear                                      |
| Source   | [`exact_k-interview-me`](../../../../home/exact_dot_agents/exact_skills/exact_k-interview-me/) |
| Routing  | manual                                                                                         |

## `k-spec`

| Field    | Value                                                                                                  |
| -------- | ------------------------------------------------------------------------------------------------------ |
| Use when | developing an idea, feature request, or bug into a compact packet with planned final acceptance checks |
| Source   | [`exact_k-spec`](../../../../home/exact_dot_agents/exact_skills/exact_k-spec/)                         |

Fork-closing consults a domain overlay's planning fork checklist when the verified target repo has one. Forks that cannot close locally (external sign-off, another team's decision) go in the packet's `External dependencies` section — owner, blocked criteria, recommended default — instead of blocking assembly; consumers must not start blocked criteria. Plan checks without running a red-check ceremony merely to approve the packet.

## `k-build`

| Field    | Value                                                                                         |
| -------- | --------------------------------------------------------------------------------------------- |
| Use when | implementing an approved spec packet through production and one integrated final verification |
| Source   | [`exact_k-build`](../../../../home/exact_dot_agents/exact_skills/exact_k-build/)              |
| Routing  | manual                                                                                        |

An already-authorized target needs no duplicate approval gate. Strong research settles material questions; implementation-band workers produce substantial settled edits; deterministic tools execute known mechanical operations. The root integrates artifacts and owns final checks and strong review/refutation. Workers do not run private QA. Commits, pushes and publication retain their separate authority requirements.

## `k-converge`

| Field    | Value                                                                                                      |
| -------- | ---------------------------------------------------------------------------------------------------------- |
| Use when | a claim or changeset should be re-attacked until a round comes back dry (mutation probes + fresh refuters) |
| Source   | [`exact_k-converge`](../../../../home/exact_dot_agents/exact_skills/exact_k-converge/)                     |
| Routing  | manual (`disable-model-invocation: true`); build/review/light-review do not invoke it automatically        |

Declare the exit (a full round with zero changes to code, tests, or published text and no unresolved findings or mutation verdicts) and the correctness-only filter (vacuous test, production bug, false published claim; everything else refused, not deferred) before round 1. Each round pins a baseline snapshot, mutates every behavioral change before arguing, fans out fresh `k-agent-adversarial-verifier` refuters on distinct dimensions, re-verifies their findings, applies in-scope fixes through the implement lane, and reruns the covering probes plus required regression checks. A changed round repeats; a dry round stops. Authorship never gates entry: on someone else's branch, the mutation and refutation steps still run against a disposable worktree and fixes come back as proposals. Close with the honest residue — what the loop never covered.

The shared `workflow-handoff.md` reference preserves the caller's frozen scope, criteria, receipts, approval and unresolved decisions. Existing read-only, ownership, compatibility, commit and publication gates remain binding; the handoff grants no extra edit, commit, push, or publication permission. No worker owns convergence or another model invocation. This is the only unbounded loop in the setup — an ordinary review fix pass is one round and must not be looped to imitate it.

## `k-text-tournament`

| Field    | Value                                                                                                      |
| -------- | ---------------------------------------------------------------------------------------------------------- |
| Use when | the user explicitly requests comparison of materially different prose alternatives against a stated rubric |
| Source   | [`exact_k-text-tournament`](../../../../home/exact_dot_agents/exact_skills/exact_k-text-tournament/)       |
| Routing  | manual (`disable-model-invocation: true`); ordinary prose edits do not trigger it                          |
| Boundary | no evaluator spawn, two-order judging, worker SELF_CHECK block, or repeated tournament per edit            |

Produce useful alternatives and explain their tradeoffs while preserving instruction safety and factual fidelity. In a larger task, alternatives belong to Understand/Produce and final assessment belongs to the existing Verify stage. Comparison stays inline unless a substantial independent production assignment warrants isolation; it never creates another verification workflow.

## `k-improve-local`

| Field    | Value                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------ |
| Use when | proposing one evidence-backed improvement to local changes                                       |
| Source   | [`exact_k-improve-local`](../../../../home/exact_dot_agents/exact_skills/exact_k-improve-local/) |
| Routing  | manual                                                                                           |

## `k-improve-branch`

| Field    | Value                                                                                              |
| -------- | -------------------------------------------------------------------------------------------------- |
| Use when | proposing one evidence-backed improvement to the current branch, PR, or issue goal                 |
| Source   | [`exact_k-improve-branch`](../../../../home/exact_dot_agents/exact_skills/exact_k-improve-branch/) |
| Routing  | manual                                                                                             |

## `k-improve-targeted`

| Field    | Value                                                                                                  |
| -------- | ------------------------------------------------------------------------------------------------------ |
| Use when | proposing one evidence-backed improvement to a targeted codebase area                                  |
| Source   | [`exact_k-improve-targeted`](../../../../home/exact_dot_agents/exact_skills/exact_k-improve-targeted/) |
| Routing  | manual                                                                                                 |

## `k-improve-codebase`

| Field    | Value                                                                                                  |
| -------- | ------------------------------------------------------------------------------------------------------ |
| Use when | proposing one evidence-backed improvement to the whole codebase                                        |
| Source   | [`exact_k-improve-codebase`](../../../../home/exact_dot_agents/exact_skills/exact_k-improve-codebase/) |
| Routing  | manual                                                                                                 |
