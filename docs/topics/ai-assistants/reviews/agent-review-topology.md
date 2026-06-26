---
sidebar_position: 1
title: Agent-review topology
---

# Multi-agent topology

`/agent-review` is the orchestration entrypoint. Cursor, Copilot, Claude, Codex, Gemini, and Amp bridge it through their native isolation mechanisms where available:

![Agent-review phase order: route, blocking PR necessity, parallel reviewers, live UI, findings audit, controller judgment, and gated action](../assets/agent-review-flow.svg)

The key invariant is phase ownership: workers investigate; the controller judges and performs any gated side effect.

| Phase                 | Starts only after                                                     | Owns                                                                                   | Stops the flow when                                                                    |
| --------------------- | --------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Route + scope         | user invokes review flow                                              | mode, authorship, target packet, constraints, intent dependencies                      | authorship/scope/intent dependency cannot be resolved safely                           |
| PR necessity / intent | route says PR + other/unknown author, or local changes need PR intent | whether the PR is worth implementation review and whether intent artifacts are current | PR is blocked, superseded, unclear, not needed, incorrectly open, or intent is unclear |
| Reviewer fan-out      | PR necessity/intent greenlight or non-applicable skip                 | read-only candidate findings and `verification_needed`                                 | both reviewers finish; individual blockers become controller input                     |
| Live UI               | reviewers finish and UI/runtime is relevant                           | UI reality, screenshot handoff, target/runtime/data blockers                           | target packet cannot be loaded or runtime is blocked                                   |
| Findings audit        | reviewer + live UI outputs exist                                      | actionability, duplication, gaps, overengineering, verification-ledger audit           | audit finds no actionable surviving finding or reports blocker                         |
| Controller judgment   | all investigation phases are complete                                 | keep/drop, serial verification ledger, PR pending-review reconciliation                | unsupported or conflicting payload would be produced                                   |
| Act                   | judgment is complete and blocking ledger items are resolved           | fixes, drafts, gated posting                                                           | human-visible gate or quality gate blocks                                              |
| Post-act verification | the working tree was edited this flow                                 | quality gates, fix-diff four-dimension stage, carried `verification_needed`            | setup itself fails or the toolchain is genuinely unavailable                           |

1. The controller resolves the route and scope packet: PR/local mode, role, target diff/PR/thread set, base branch, user constraints, expected output, and any intent dependencies needed for judgment.
2. For other-authored or unknown-author PRs, `pr-necessity-auditor` runs first and blocks fan-out until it greenlights implementation review. It also runs as an intent audit for local changes attached to an assigned/adopted PR when PR body, discussion, Slack, issues, or history are needed to judge the local diff.
3. After any required PR necessity greenlight, two read-only reviewer workers run in parallel when the harness supports it.

PR necessity checks:

- whether the PR is sensible.
- whether it is correctly open.
- whether the work is still needed.
- whether overlapping open/recently merged work exists.
- author intent from PR, references, history, and available GitHub/Slack context.

Review greenlight is separate from merge readiness. Unknown mergeability or failing status checks are reported as status uncertainty, not as "no conflicts".

Reviewer lanes are investigation-only:

- they may run deep non-mutating verification.
- they do not edit the worktree.
- they do not seed data or start shared services.
- they do not run generators/formatters/installers.
- they return `verification_needed` when stronger evidence requires mutation or a shared runtime.

The controller tracks those entries in a verification ledger. A ledger item that can flip a keep/drop/action decision stays blocking until it is resolved with evidence, run serially, or reported as an explicit blocker. Findings audit can recommend a disposition, but it cannot erase the dependency or turn an unresolved fork into "not needed" by assuming one branch.

Reviewer lane mapping:

| Runtime        | Worker lanes                                                         |
| -------------- | -------------------------------------------------------------------- |
| Cursor/Copilot | GPT and Opus                                                         |
| Claude         | `reviewer` twice through `Task` with Claude model overrides          |
| Codex          | `spawn_agent` roles; two `review-worker` agents with distinct angles |
| Gemini         | `review-gemini-pro` and `review-gemini-flash`                        |
| Amp            | two generic `Task` subagents with the shared worker contract         |

1. `live-ui-review` checks applicable UI/runtime candidates with Playwriter against a controller-supplied target packet.
2. The findings audit runs after live UI before any action. The controller audits inline for trivial sets (zero or one straightforward finding with no disagreement/blocker/fix diff) and delegates to `findings-auditor` for non-trivial sets, including material `verification_needed`. It flags redundancy, verbosity, semantic + logical duplication, gaps, actionability problems, overengineered proposed fixes, and verification-ledger disposition problems. When both reviewer lanes report the same root cause, the audit should merge/dedupe it into one candidate unless hard evidence proves a drop reason.
3. The controller aggregates the investigation outputs, then judges what to fix or draft through mode-correct review rules. For each ledger item, it either resolves it with evidence, runs the check serially when needed for judgment, marks it not needed with evidence, or reports the exact blocker/uncertainty. Drop decisions need a source/API/runtime-backed hard reason; otherwise the controller keeps the finding, merges it with a duplicate, runs needed verification, or blocks with explicit uncertainty. PR modes use PR dedup, PR artifact truth filtering, the PR necessity/correctly-open greenlight, and PR CI coverage gates; local changes are judged against the staged/unstaged/range scope without PR-thread or PR-CI exemptions unless a PR-intent dependency is required for the local diff.
4. Before final PR-mode drafting or posting, the controller reconciles against existing review feedback already authored by the current account: API `PENDING` reviews and draft comments, plus submitted review comments/replies from previous sessions. It merges still-valid pending feedback with net-new findings into one payload, drops stale pending findings, and blocks rather than producing conflicting or fragmented review comments. Only the controller acts.

Live UI can return:

| Result              | Meaning                                                                           |
| ------------------- | --------------------------------------------------------------------------------- |
| comparison evidence | UI/runtime finding is verified                                                    |
| screenshot handoff  | focused local screenshots under `/tmp`, reported separately for manual attachment |
| `Not applicable`    | target does not apply to the introduced surface                                   |
| blocker             | target, branch, runtime, or data setup is missing                                 |

For verified `elastic/kibana` targets, `elastic-domain` supplies Kibana targets, mapped Elasticsearch endpoints, Dev Tools Console fallback, and runtime-blocker rules. Generic review contracts do not inline those targets.

For UI-facing PR findings with screenshot evidence, the controller keeps image paths out of GitHub review bodies and reports a separate `UI evidence attachments:` handoff with local paths, descriptions, target branch/URL, and suggested comment placement.

Runtime model names are not portable:

| Runtime     | Review lanes                                                    |
| ----------- | --------------------------------------------------------------- |
| Cursor      | `gpt-5.5-extra-high` / `claude-opus-4-8-xhigh`                  |
| Copilot     | `gpt-5.5` / `claude-opus-4.8` plus `effortLevel: xhigh`         |
| Claude      | `Task` reviewer lanes with Claude model overrides               |
| Codex / Amp | two-worker isolation and distinct angles, not exact Opus parity |
| Gemini      | native subagents; main Gemini session remains controller        |

Cursor agents pin model frontmatter because omitted `model` inherits the parent/default model, which can be `composer-2.5-fast`.

Controller responsibilities:

- route and scope.
- run PR necessity gate when required.
- fan out after greenlight.
- run live UI.
- audit findings inline or by delegation.
- aggregate, filter, and reconcile pending-review context.
- act after normal gates: apply fixes when `fix_authorized: yes` (own, assigned, adopted PR, or local-changes self flow), otherwise draft only.
- run post-act verification whenever the working tree was edited: quality gates plus the fix-diff four-dimension stage.
- restart from the earliest invalidated phase when the user supplies new context that changes target, intent, or accepted behavior; if leaving `/agent-review`, state that downgrade before editing.
- block completion while decisive verification-ledger items, intent dependencies, pending-review reconciliation blockers, required live-UI triggers without valid blockers, or post-act verification items remain unresolved.

Worker profiles are read-only, concurrency-safe, and recursion-safe. They load review methodology in isolated contexts and return candidate findings plus `verification_needed`.

Each delegated phase emits a `Worker selection:` line before launch with the phase, profile, task agent type, model, named/fallback invocation, and fallback reason. This keeps markdown session exports auditable even when the runtime hides raw task arguments.

When a phase needs a follow-up turn in an existing worker, the controller sends the follow-up and waits for the completion notification instead of repeatedly polling with long `read_agent` waits. The phase remains blocking, but the controller does not burn time on status checks.

Live UI target selection:

| Case                                           | Behavior                                          |
| ---------------------------------------------- | ------------------------------------------------- |
| explicit user/repo target packet exists        | use it                                            |
| no explicit target and verified Kibana applies | use `elastic-domain/references/kibana-live-ui.md` |
| no target packet can be loaded                 | block instead of inventing targets                |

![Live UI target-packet handoff: controller selects an explicit or verified overlay packet, worker verifies, and returns evidence, not applicable, or blocker](../assets/live-ui-target-packet.svg)
