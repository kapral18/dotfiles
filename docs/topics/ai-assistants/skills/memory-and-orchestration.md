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

`k-proof` is available in two ways. Explicit receipt requests route through the skill frontmatter and `SKILL.md`. Non-review/non-build iteration gets the same narrow receipt gate from the always-on SOP and the shared verification prefix that `perturn_recall.py` re-injects after a compaction. The ledger is a durable receipt, not verification itself: evidence collection remains mandatory and inline by default. When a receipt trigger applies, choose the topic and criteria before ledger-bound evidence collection, finalize the ledger, and only then generate a report.

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

Fork-closing consults a domain overlay's planning fork checklist when the verified target repo has one. Forks that cannot close locally (external sign-off, another team's decision) go in the packet's `External dependencies` section — owner, blocked criteria, recommended default — instead of blocking assembly; consumers must not start blocked criteria. Plan checks without running a red-check ceremony merely to approve the packet. The packet also carries an impact map (affected callers/consumers, invariants, co-edit set) from the SOP §3.1 shared assessment; `none` requires the light-path proof.

## `k-build`

| Field    | Value                                                                                         |
| -------- | --------------------------------------------------------------------------------------------- |
| Use when | implementing an approved spec packet through production and one integrated final verification |
| Source   | [`exact_k-build`](../../../../home/exact_dot_agents/exact_skills/exact_k-build/)              |
| Routing  | manual                                                                                        |

An already-authorized target needs no duplicate approval gate. Strong research settles material questions; implementation-band workers produce substantial settled edits; deterministic tools execute known mechanical operations. The root integrates artifacts and owns final checks and strong review/refutation. Workers do not run private QA. Every co-edit-set member named in the impact map is updated in the same change or recorded as unaffected with evidence, and the final criteria verification checks that. Commits, pushes and publication retain their separate authority requirements.

## `k-formal`

| Field    | Value                                                                                                                                                                                                                                                           |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Use when | SOP §3.6 selects a stateful or parser-like verification tier: author, diagnose, or review a `,formal` catalog unit                                                                                                                                              |
| Source   | [`exact_k-formal`](../../../../home/exact_dot_agents/exact_skills/exact_k-formal/)                                                                                                                                                                              |
| CLI      | `,formal` builds and audits a persistent, diff-aware unit catalog under `$AGENT_FORMAL_HOME`, `$XDG_STATE_HOME`, or `~/.local/state`: anchored transition table → Lean model → exhaustive search → mutants → trace replay, with proofs added only at tier F3    |
| Boundary | pure input→output behavior stays on the disposable independent-oracle harness (SOP §3.6) only when production tests cannot express the cases; workers author units in Produce without compilation or direct adapter-smoke checks; the root owns audit in Verify |

Research extracts transition rows and proposes anchor ranges without writing catalog state; the root or another explicitly authorized execution category persists anchors and runs diagnostic `traces`/`replay` during Understand, while research analyzes the returned output. Implement authors the Lean model, properties, discriminating mutants, and replay adapter. In Verify, only the root runs useful cheap prerequisites and `,formal audit <unit> --json` once per exact snapshot and inputs. Default audit build ordering gates dependent expensive stages; custom requirements do not universally normalize prerequisites. The root reports executable conformance and anchored fidelity separately, including real-consumer observed fields and init-rooted defect/preserved-invariant witness coverage; when cover traces omit a defect schedule, targeted regression/replay evidence or the gap is reported. It reports `certifies` verbatim and saves only from that current passing receipt. Anchor validity permits model/version reuse across branches, worktrees, or squash merges; it does not keep an old audit current. Edits invalidate affected judgment, not unrelated evidence. Existing stale work dirs are repaired in place, while checkout is only for a valid resolved version when no work dir exists.

## `k-converge`

| Field    | Value                                                                                                                 |
| -------- | --------------------------------------------------------------------------------------------------------------------- |
| Use when | a claim or changeset should be re-attacked until a round comes back dry (mutation probes + fresh refuters)            |
| Source   | [`exact_k-converge`](../../../../home/exact_dot_agents/exact_skills/exact_k-converge/)                                |
| Routing  | model-invocable only on an explicit user request for the loop; build/review/light-review never start it automatically |

Declare before round 1: the exit, correctness-only filter, threat model, scope, finite round cap (3 unless the user sets another), severity floor, and slow oracles. Each round pins a baseline snapshot and mutates behavioral changes before arguing. Round 1 refutes all four dimensions; later rounds select dimensions from the fix's dependency and claim impact, not file extension alone. Retain a prior dimension result only when its surface and every supporting dependency are unchanged. In-scope fixes go through the implement lane, followed by covering probes and the full retained-scope checks.

The shared `workflow-handoff.md` reference preserves the caller's frozen scope, criteria, receipts, approval and unresolved decisions. Existing read-only, ownership, compatibility, commit and publication gates remain binding; the handoff grants no extra edit, commit, push, or publication permission. No worker owns convergence or another model invocation. The user-invoked `k-converge` loop is the only multi-round loop in the setup — an ordinary review fix pass is one round and must not be looped to imitate it.

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
