---
name: k-agent-review
description: "Manual-only controller contract for /agent-review multi-agent review fan-out, findings aggregation, and gated fixes/comments."
disable-model-invocation: true
---

# Agent Review

This is the controller contract for `/agent-review`.

The controller:

- routes
- delegates
- aggregates
- judges
- performs gated side effects

The substantive review work happens in isolated reviewer workers that load the shared `k-review` skill themselves.
Two exceptions: the blind fresh-eyes clarity lane loads none of it (`references/fresh-eyes.md`), and the adversarial verifier loads only `judging_core.md` (`references/adversarial-verifier.md`).

The reviewer-worker lanes are read-only:

- no working-tree edits
- no shared-state mutations or state-changing verification commands
- no live-UI checks
- no posting or resolving
- no commits or pushes
- no fix application

Workers may run non-mutating verification at whatever depth is needed to find and validate review findings.
Parallel lanes must not mutate shared runtime state.
That includes the working tree, repo-local caches, databases, dev services, browser state, GitHub, and git state.
Use unique `/tmp` paths or isolated copies for disposable reproduction artifacts.
Apply the SOP rules about internal time/effort estimates inside this read-only boundary.
If a finding needs shared-state mutation, a shared service, or another exclusive resource to verify, return the verification need to the controller.
Do not do that verification inside any parallel lane.

Workers only investigate and return candidate findings or `verification_needed`.

All side effects happen later in the controller, gated by the final act phase.

The `k-review` skill and its references remain the source-of-truth methodology workers load read-only.

## Controller boundary

The controller owns:

- route and scope discovery:
  - mode: local changes, PR review, or PR fix
  - authorship: `self` / `other` / `unknown`
  - PR number or diff range
  - base branch
  - staged/unstaged state
  - thread IDs
  - user constraints
  - expected output shape
  - intent dependencies needed for judgment, if any: PR body, PR discussion/review threads, linked issues/PRs, Slack threads, design artifacts, commit messages, or branch history
- running the conditional blocking `pr-necessity-auditor` before implementation review
  - applies to other-authored/unknown PRs
  - applies to local flows with a PR-intent dependency
- launching the reviewer workers after any required PR necessity greenlight: the angle lanes plus the conditional blind fresh-eyes clarity lane
- running the cross-family adversarial verification pass over the merged candidate set after every reviewer lane returns
- running conditional `live-ui-review` verification after adversarial verification returns
  - applies when changed paths or kept candidate findings touch UI/runtime behavior
  - requires applicable runtime evidence
  - requires screenshot handoff evidence for any UI-related finding that may become draft review feedback, unless live UI returns a valid blocker or non-applicability result
- running the findings audit phase after live UI returns evidence/non-applicability/blocker or is explicitly skipped;
  delegate to `findings-auditor` only when a step 6 delegation condition is true
- aggregating worker outputs, `pr-necessity-auditor` status, reviewer findings, adversarial verification verdicts, live UI status/evidence/artifacts/skip reason, and audit output
- deciding which worker-reported `verification_needed` items deserve serial controller verification
- judging kept/dropped findings after aggregation
- reconciling PR-mode draft payloads before preparing or posting final review feedback
  - compare against existing current-account pending reviews, submitted review comments, and replies
- applying fixes, drafting payloads, or touching GitHub only after the relevant `k-review`/`communication`/`github`/`git` gates
  - load `k-communication` before wording any human-visible draft

Before fan-out, the controller must not load or run the full `k-review` skill.

It may load only one router section first:

- Resolve `authorship` using the review router's Role Detection procedure (`~/.agents/skills/k-review/SKILL.md`).
- Do this before any worker launch because the PR necessity gate and final act phase depend on that value.
- Do not infer authorship from the change being checked out locally.
- A branch tracking another person's fork is `other`.
- Commits authored by someone else are `other`.
- If authorship cannot be verified, it is `unknown`.

Before fan-out, the controller may only gather route/scope, authorship, fix authorization, PR metadata needed for routing, and the base-context preflight.
Do not run implementation review analysis in the controller before reviewer launch.
That includes semantic code search (`semantic_code_search`, `symbol_analysis`, `map_symbols_by_query`, `read_file_from_chunks`), coverage checklists, and candidate-finding investigation.
`list_indices` is allowed only to earn the `Base context:` line.

If a local-changes flow is attached to, assigned from, or adopted from a PR and the controller would use PR intent/scope to keep, drop, or fix a finding, treat that as a blocking intent dependency.
Resolve it through the PR necessity/intent audit with the complete artifacts, or carry it as explicit uncertainty.
Do not act from stale PR body or commit-title evidence alone.

After workers return, the controller may consult only the minimum relevant review references for:

- deduplication
- severity
- Replacement/Migration Parity Gate classification from `judging_core.md`
- side-effect gates
- `~/.agents/skills/k-review/references/pr_common.md` for PR-mode reconciliation
- `~/.agents/skills/k-review/references/shared_rules.md` for existing pending-review awareness

Do not rerun the coverage checklist, base-context investigation, or worker review analysis.

Reviewer workers own the full investigation methodology.

- Role-specific runtime contracts live under `~/.agents/skills/k-agent-review/references/`.
- Load inside each worker context:
  - `~/.agents/skills/k-review/SKILL.md`
  - `~/.agents/skills/k-review/references/judging_core.md`
  - `~/.agents/skills/k-review/references/shared_rules.md`
  - selected mode file under `~/.agents/skills/k-review/references/`
  - `~/.agents/skills/k-review/references/pr_common.md` for PR modes
- Return only evidence, candidate findings, and any `verification_needed` entries that were unsafe or required shared-state mutation/contention inside a parallel lane.
- Never edit, post, resolve, commit, push, or decide what should be fixed/commented on.
- The blind fresh-eyes lane is the exception to the load list above: it loads only `~/.agents/skills/k-agent-review/references/fresh-eyes.md` and must not load the `k-review` skill or any PR context.

The active harness owns subagent discovery and invocation.

- Read `~/.agents/skills/k-agent-review/references/runtime-harnesses.md` only for capability caveats.
- Never invent a custom-agent layer the harness does not expose.

## Default orchestration

The phase order is strict:

1. route and scope
2. blocking PR necessity/intent gate, only when step 2 triggers
3. the reviewer angle fan-out in parallel (registry-model angle lanes plus the blind fresh-eyes clarity lane when it applies)
4. cross-family adversarial verification over the merged candidate set
5. live UI verification when changed paths or a non-refuted candidate touch UI/runtime behavior
6. findings audit, inline or delegated by the step 6 delegation conditions
7. controller aggregation, judgment, PR-mode pending-review reconciliation, and action
8. post-act verification, only for any flow that edited the working tree (gates + fix-diff Post-Review Stage)

Do not start a later phase until the current phase returns.
In blocking phases, do not poll background workers with long waits just to check status;
wait for completion notifications or use the harness's synchronous/blocking mechanism.
If the harness cannot await background workers by id (for example Cursor), apply `runtime-harnesses.md`;
launch the worker as the harness's real background subagent, then wait only through a harness-native subagent completion signal.
Never loop blind fixed-interval sleeps waiting on a subagent.
The same rule applies after `write_agent` follow-ups for addenda or reconciliation checks:
send the follow-up, state that the phase is waiting, and end the turn unless the worker has already completed.
The controller may read completed phase outputs, but it must not perform later-phase analysis while the current phase is still running.

For every delegated worker, emit an export-visible worker selection line before launch:

```text
Worker selection: phase=<pr-necessity|review:<angle>|fresh-eyes|adversarial-verify|live-ui|findings-audit>, profile=<configured profile name>, agent_type=<task/subagent agent type>, model_required=<model-or-n/a>, model_used=<model-or-n/a>, model_status=<exact|unavailable|n/a>, tool_readonly=<false|n/a>, launch_wait=<blocking|background|n/a>, invocation=<named|fallback>, fallback_reason=<none or reason>
```

This line is part of the audit trail.
If a runtime export hides task arguments, the worker selection line must still prove whether the controller used named profiles.
It must also show any fallback such as `general-purpose`.
A worker launch is invalid when `model_required` differs from `model_used` or `model_status` is not `exact`, unless the phase is explicitly `n/a` for model selection.
The fresh-eyes phase is not `n/a`: generic fresh-eyes is the only lane launch that passes the registry lane model at runtime because no named profile carries its model frontmatter.

1. **Route and scope.** Build a scope packet with:
   - mode: `local_changes.md`, `pr_review.md`, or `pr_fix.md`
   - `authorship`: `self`, `other`, or `unknown`
   - PR number or diff range
   - base branch
   - staged/unstaged state
   - thread IDs
   - user constraints
   - expected output shape
   - intent dependencies needed for judgment, or `none`
   - lane/verifier models: the `agent_review_models` registry values rendered into the deployed profiles;
     worker selection lines emit `model_required=<registry value|inherit|default>` and the launch-confirmed `model_used`

   Resolve `authorship` via the review router's Role Detection. Do not duplicate worker review analysis in the controller.

Resolve `fix_authorized` (the working-tree-edit permission for this run) once here, alongside `authorship`.
It is `yes` when any of these hold:

- `authorship: self` (your own PR, or a local-changes flow);
- you are the PR assignee (verify via `gh pr view --json assignees`);
- the user explicitly states takeover/adoption intent for the PR
  - examples: "I'm taking this over", "my PR now", "fix what's missing", "take over this branch", or equivalent

When `fix_authorized: yes`, the fix step does NOT require a separate "fix" keyword —
an adopted/assigned/own PR is fix-authorized by virtue of ownership, not phrasing.
When none of the above hold (`authorship: other`/`unknown` and no assignee/takeover signal), `fix_authorized: no`:
draft-only, never edit code. Record `fix_authorized` in the scope packet; step 9 branches on it.
`fix_authorized` governs only working-tree edits and verification mutations.
It never authorizes commit/push/post/resolve, which keep their own explicit-approval gates (git/github skills + Human-Visible Publication Gate).

Run the base-context preflight before fan-out.
The Base-Branch Context Gate in `~/.agents/skills/k-review/references/shared_rules.md` is blocking and controller-owned.
Read-only reviewer workers run with MCP/SCSI disabled and structurally cannot run it.
You MUST invoke `list_indices` yourself, trying both `scsi-main` and `scsi-local`.
Select the repo-matching index or prove none exists, and only then emit the `Base context:` line.
The line must use the real `<reason>`: `SCSI used` / `not indexed` / `tools unavailable` / `user-selected none`.
Never assert a `Base context: SCSI=none` line that you did not earn by running `list_indices`.
If your own runtime also blocks `list_indices`, say so explicitly as `tools unavailable` rather than implying the gate ran.
Do not use the base-context preflight as a loophole for implementation analysis:
no `semantic_code_search`, symbol analysis, code-chunk reads, broad code investigation, or finding construction before reviewer workers launch.

1. **Run conditional blocking PR necessity/intent audit.**
   - Run `pr-necessity-auditor` before any implementation reviewer when:
     - mode is `pr_review.md` or `pr_fix.md`, and
     - `authorship` is `other` or `unknown`.
   - Also run it as a blocking PR intent audit when all of these hold:
     - mode is `local_changes.md`,
     - the local changes are attached to, assigned from, or adopted from a PR, and
     - PR intent/scope artifacts are needed to decide whether a local change is correct, stale, or fixable.
   - Invoking `/agent-review` is the request for this PR meta-audit; do not require a second user opt-in.
   - Skip it for local changes and self-authored PRs only when PR intent/scope is not needed for controller judgment.
   - This worker is read-only and evidence-only.
   - Give it the scope packet plus the PR URL/number, base/head refs, changed paths, directly referenced issues/PRs, and any already-known user constraints.
     Include linked Slack/design artifacts already known to the controller.
   - It must follow `~/.agents/skills/k-agent-review/references/pr-necessity-auditor.md`.
   - It returns one of:
     - `Not applicable`
     - greenlight evidence that the PR is sensible enough to review further
     - blocker or stop status for inaccessible GitHub, Slack, history, unclear intent, not-needed/superseded work, or incorrectly-open status
   - Greenlight means there is no unresolved blocker and no supported classification that makes implementation review premature or unnecessary.
     For other-authored or unknown-author PRs, continue to reviewer fan-out only when the audit supports `needed: yes`.
     Also require no material correctly-open/intent concern blocking review.
   - Greenlight is not merge readiness.
     Failed/missing labels, outdated-branch checks, unknown mergeability, or other status blockers may be surfaced as `merge_readiness`/status uncertainty.
     These can still allow implementation review to continue.
   - Never treat `mergeable: UNKNOWN`, `mergeStateStatus: UNKNOWN`, or missing merge metadata as proof of no conflicts.
     Record it as unknown.
   - If the audit returns blocked, unclear, not needed, superseded, incorrectly open, or leaves an intent dependency unresolved, stop the implementation review flow.
     Surface the supported blocker/PR-level draft feedback.
     Do not launch reviewer workers, live UI, or findings audit unless the user explicitly asks to continue anyway.
   - Do not rely on the auditor to decide or post. The controller judges and gates any draft feedback.

2. **Launch the reviewer angle fan-out in parallel.**
   - Build the angle roster from scope-level evidence only (mode, changed paths, `git diff --stat`, `--diff-filter=D` status);
     roster selection is not implementation analysis — do not read code bodies for it.
     - Always include `correctness/regressions`.
     - Add each angle the change surface implicates:
       - tests/validation: test files touched, or risky logic changed with no test changes
       - simplicity/maintainability: large refactors, renames, or structural churn
       - types/API contracts: public API/type-surface paths
       - security: auth/permission/input-handling/crypto/secret paths
       - performance: hot paths, queries, data-volume loops
       - deletion-safety: deleted files/exports (`git diff --diff-filter=D --stat` non-empty)
       - state-machine behavior: parser/workflow/retry/permission-matrix/multi-flag paths
       - product flow/user-visible behavior: UI components, routes, user-state, API handlers serving UI
       - observability/signal quality: alerting/monitoring/threshold/telemetry/query-generation paths
     - Launch two to five angle lanes — always at least two, even for a single-concern diff (pick the two most load-bearing angles), so no finding class depends on one lane.
     - If more angles are implicated than five, fold the extras into the closest launched lane as stated secondary emphases.
     - State the roster and the scope-level evidence for each selection in the output.
   - Lane model selection is declarative, never steered at runtime: every deployed profile's `model` frontmatter is rendered from the single `agent_review_models` registry in the chezmoi model data (a concrete id, `inherit`, or omitted for the harness config default).
     The controller launches named profiles as-is and never passes lane model overrides;
     the exception is the blind generic fresh-eyes task, which must pass the same registry lane value as the profile-equivalent model because it cannot use the named reviewer profiles.
     A wrong or stale model is fixed in the registry, not the launch.
     The angles are this phase's diversity axis; cross-family checking is owned by the adversarial verification phase.
   - Emit all reviewer-lane launches, fresh-eyes included when it applies, in one message (a single tool-call batch).
   - Use the harness's native reviewer worker profiles or task mechanism (`review-worker`/`reviewer` profiles, or a generic task type carrying `reviewer-worker.md`); read `runtime-harnesses.md` for per-harness launch and model-inheritance caveats.
   - Hard-read-only caveat: for Cursor, follow `runtime-harnesses.md`.
     Cursor Task launches and Cursor profile shims for `/agent-review` must use `readonly: false`.
     If a worker reports Ask/read-only mode blocked shell/git/`gh`/SCSI/Playwriter, discard that launch result and rerun with `readonly: false`.
   - Cursor Task background caveat: reviewer, PR-necessity, live-UI, and findings-audit workers should remain real Cursor background subagents.
     Use Cursor Task `run_in_background=true` for those launches when the active Cursor Task schema exposes it.
     Do not use shell `Await`/`AwaitShell` with Cursor subagent ids; wait through a Cursor-native subagent completion signal.
     If no native completion signal is available, end the controller turn and wait for the completion notification, or do one transcript completion check; never repeated sleep polling.
   - Give each worker the scope packet and one angle from the roster above.
   - If `runtime-harnesses.md` says the active harness cannot fan out from the current context, run them as that file directs and state why.
   - This phase is blocking as a phase.
     After the reviewer workers are launched, do not start adversarial verification, live UI verification, findings audit, or controller judgment until every launched lane's output is available, fresh-eyes included when it was launched.
   - Keep the parallel lanes concurrency-safe:
     - Prefer file reads, local source inspection, SCSI/base-context queries, `git show`/`git diff` reads, isolated `/tmp` reproductions, and verification commands.
       The verification commands should improve finding validity or coverage.
     - Allow non-mutating verification at whatever depth is needed, including expensive static analysis or full suites.
       Outputs/caches must be read-only or isolated away from shared repo/runtime state.
     - Do not start dev servers, watchers, database migrations, package installs, code generators, formatters, fixture seeders, or cache/artifact-writing commands from reviewer lanes.
     - If stronger verification requires shared-state mutation, a shared service, or an exclusive runtime resource, return `verification_needed` with the exact command/setup.
       Let the controller run it serially after aggregation or during the act phase.
   - Each candidate finding must include a reachability statement for the claimed path.
     If the claimed UI/API/state path may be unreachable, the worker must verify reachability before assigning severity or mark it as a hypothesis for the controller to verify/drop.
   - **Blind fresh-eyes clarity lane (conditional, same launch batch).**
     - Launch an additional read-only worker on `~/.agents/skills/k-agent-review/references/fresh-eyes.md` when the mode is `pr_review.md` or `local_changes.md` and the diff adds or changes human-maintained code or docs.
     - Skip it for `pr_fix.md` (thread-driven), and when the diff touches only generated/vendored/lockfile content; record the skip reason.
     - Blindness is this lane's diversity axis.
       Its packet is only the diff scope (base ref, changed paths, or an explicit diff command) —
       never the PR number/title/body, commit messages, issue text, thread content, prior findings, or controller narrative.
     - Launch mechanics, allowed reads, and the worker selection line fields are owned by `fresh-eyes.md`;
       do not launch it through the named reviewer profiles, which preload the `k-review` skill and PR context.
     - This lane is part of the phase-3 barrier: adversarial verification, live UI, findings audit, and judgment wait for it like any reviewer output.

3. **Run adversarial verification on the merged candidate set.**
   - After every launched reviewer lane returns, collapse same-root-cause/same-anchor duplicates into one merged candidate each (merge/dedup only; no new controller investigation).
   - If the merged set is empty, skip this phase and report `Adversarial verification: skipped (no candidates)`.
   - Launch one adversarial-verifier worker following `~/.agents/skills/k-agent-review/references/adversarial-verifier.md`.
     Give it the merged candidates with lane attribution stripped, plus the diff scope, base ref, and mode.
   - Model rule — the one lane where model identity matters: the `agent_review_models` registry assigns each harness a verifier model from a different family than its lane model (the pairing is reviewed by a human in the registry, not inferred at runtime), and the deployed `adversarial-verifier` profile carries it (Pi: the controller passes the rendered registry value per task).
     Harnesses whose registry entry is empty/`inherit` (single-family surface) run the verifier on the lane model with the contract's refutation framing and report `families=same (degraded)`.
     Degradation must be reported, never silent; do not skip the phase because cross-family is unavailable.
   - Verdicts are evidence, not decisions: when recording each `confirmed` / `refuted` / `undecidable (needs <check>)` in the verification ledger, check that a `refuted` verdict's evidence addresses the candidate's actual claim; record it as `undecidable` otherwise.
     "Non-refuted" downstream means not validly refuted after that check.
   - This phase is blocking before live UI so refuted candidates do not trigger runtime verification.

4. **Run conditional live UI verification.**
   - After adversarial verification returns (or is skipped with no candidates), first apply a read-only controller parity filter to replacement/test-migration candidates:
     - apply the Replacement/Migration Parity Gate from `judging_core.md` to replacement/test-migration candidates
     - drop candidates classified as `preserved_limitation` or `prose_drift`
     - do not treat test-only UI code as live-UI applicability by itself
   - Run `live-ui-review` when changed paths or any non-refuted candidate touch UI/runtime behavior and runtime evidence is applicable.
     For replacement/test-migration candidates, only `parity_gap`, `new_regression`, and `scope_expansion` can be kept candidates for this trigger.
   - A deterministic, unit, integration, or other-layer proof does NOT discharge a live-UI trigger when the runtime is startable.
     Examples include a resolution/compile harness, a passing test, or a static trace;
     these are corroborating evidence, not substitutes for live verification.
     Once the trigger fires, skipping live UI is valid only via a packet-defined blocker.
     Valid blockers include a read-only/Ask-mode harness, an unstartable runtime, or another blocker the selected target packet recognizes.
     Do not skip because a non-runtime proof already exists or because runtime evidence is judged "unlikely to change the verdict".
     If the runtime is startable (runtime-start rung), start it and verify.
   - Hard runtime read-only/sandbox modes are not the review safety boundary.
     Use harness permissions that allow the lane's permitted verification tools, and enforce no-mutation behavior through the role contract.
   - Use those permissions only for the lane's permitted verification tools: read-only shell/git/`gh`/SCSI for investigation workers, or Playwriter/browser commands for `live-ui-review`.
     `live-ui-review` may also run explicit local/dev runtime data setup against verified targets.
   - Mode boundary: default `live-ui-review` is verification-only.
   - Keep behavior-level read-only constraints in the prompt:
     - no repo edits
     - no file writes except Playwriter artifacts under `/tmp`
     - no GitHub mutations
     - no git writes
     - no commits or pushes
   - For post-fix UI verification, launch a separate fix-capable Playwriter task after judgment.
   - A domain overlay is a repo/org-specific skill selected from the verified target repo/org, not guessed from wording.
     For live UI, an overlay may provide a concrete target packet; the worker receives the packet, not an unresolved overlay concept.
   - Select a live UI target packet before launch:
     - If the target repo/object is verified as `elastic/kibana` and no explicit user-provided or repo-documented local/dev target packet exists, load `~/.agents/skills/k-elastic-domain/SKILL.md`.
       Include the Kibana live-UI target packet from `~/.agents/skills/k-elastic-domain/references/kibana-live-ui.md`.
     - Otherwise use the explicit user-provided or repo-documented local/dev target packet.
   - Resolve target worktree identity before launch:
     - `controller_cwd` is where the review controller happens to run; it is not automatically the PR/head runtime.
     - `reviewed_head_worktree` is the checkout that contains the code under review for the PR/head branch/sha.
     - For local-changes mode, the current worktree may be `reviewed_head_worktree` only when it contains the changed code being reviewed.
     - For an explicit PR/branch review invoked from another checkout (especially a base/main checkout), do not use `controller_cwd` as the PR/head target unless it is checked out to the reviewed PR/head branch/sha.
       Reuse or create a worktree for the reviewed PR/head branch before live UI, or return a target-worktree blocker with the exact command/setup required.
     - Base/main is comparison-only: resolve/start a base target only when a distinct `reviewed_head_worktree` exists and the target packet requires base-vs-head comparison.
     - Identify which running runtime is head vs base only from the target packet's registry/discovery keyed by worktree path;
       never decide head-vs-base by probing a port (e.g. `curl localhost:5601`), which silently mistakes an already-running base/main stack for the head runtime.
   - Resolve required runtime config once, before the first `live-ui-review` launch:
     from the changed paths and kept candidates, determine any runtime/feature-flag settings the path under review needs to be reachable.
     Pass them to the worker so the runtime is started correctly the first time instead of started default and reconfigured after a blocker.
     The concrete settings and the start-time mechanism are owned by the selected target packet.
     For example, the Kibana overlay owns `required_kbn_flags` -> `,kbn-stack -K`;
     keep specific flag names and values in the packet/overlay, not here. When none are needed, pass an empty set.
   - Include the selected target/preflight packet and the resolved required runtime config in the worker prompt.
   - Do not rely on the worker to rediscover it.
   - Windows/VirtualBox coverage is out of scope for this flow: `live-ui-review` verifies the local browser only.
     When the user explicitly wants Windows/VirtualBox coverage too, add the manual `~/.agents/skills/k-live-ui-windows/SKILL.md` skill to this turn's work by hand; never infer it from PR/issue context.
   - It returns one of:
     - `Not applicable`
     - comparison evidence with `ui_evidence_artifacts`
     - target/branch/runtime/data blocker for the controller to surface
   - For an applicable UI-related candidate that may become draft review feedback, screenshots are required supporting evidence.
     If `live-ui-review` confirms or materially supports the candidate without screenshot handoff entries, rerun the worker or carry a blocker; do not draft the comment from text-only UI evidence.
   - Do not automatically rerun a blocked live-UI result except for a missing/un-started local runtime in a shell-capable harness when the selected target packet documents a start command.
     That case is the runtime-start rung, not a terminal blocker; have the runtime started and rerun rather than surfacing it as remaining uncertainty.
   - A read-only/Ask-mode Playwriter block is a valid blocker to surface.

5. **Run findings audit on candidate findings.**
   - Run this phase only after the PR necessity gate, every launched reviewer-lane output (fresh-eyes included when launched), the adversarial verification verdicts or skip status, and the live UI result or explicit live-UI skip reason are available.
   - Always audit kept reviewer findings (fresh-eyes clarity candidates included), adversarial verification verdicts, worker-reported `verification_needed`, live UI evidence/artifacts/blockers or skip reason, and kept PR necessity draft concerns.
     Include only PR necessity concerns kept after the greenlight gate.
   - Maintain a verification ledger for every worker-reported `verification_needed` and every live UI / PR necessity blocker that can affect keep/drop/action.
     The findings audit may recommend dispositions, but it must not erase a ledger item by assuming one branch of an unresolved fork.
   - If two or more reviewer lanes report the same or overlapping root cause, treat that as a merge/deduplication task, not as evidence that the issue is unnecessary.
     Collapse duplicates into one candidate and keep verifying/judging it unless a hard drop rule below is proven.
   - Inline the audit in the controller when the remaining set is trivial:
     - no candidate findings, or
     - one straightforward evidence-backed finding with no lane disagreement, no live UI blocker, no PR-necessity concern kept after greenlight, and no fix diff to audit.
   - Delegate to `findings-auditor` when the remaining set is non-trivial:
     - two or more candidate findings
     - any HIGH/CRITICAL candidate
     - lane disagreement (including finder-vs-verifier disagreement) or likely duplication
     - any worker-reported `verification_needed` required to decide whether to keep or drop a candidate
     - any PR necessity concern kept after greenlight
     - live UI comparison/blocker evidence or screenshot handoff needed to decide whether to keep or drop a candidate
     - any named fix diff, staged set, or applied-fix diff
     - any proposed fix that may be overengineered or cross-cutting
   - Audit for:
     - redundancy
     - verbosity
     - semantic + logical duplication
     - gaps
     - actionability of the remaining findings and proposed fixes
     - overengineering risk in proposed fixes
   - This is still investigation, not a decision, even when inlined in the controller.
   - If inlined, still report the audit result in the final output as `Findings audit: inline ...`.
   - For fix-capable own/self-review flows, this pre-action audit does not replace the normal post-review stage over the actual fix diff after fixes are applied.
6. **Aggregate.**
   Combine `pr-necessity-auditor` greenlight/skip status, each angle lane's output, fresh-eyes output or its skip reason, the adversarial verification verdicts and family status, the verification ledger, live UI evidence/status/artifacts, and the findings audit result.
7. **Judge in the controller.**
   - Apply mode-correct reconciliation:
     - all modes: collapse duplicate worker findings, apply the severity model, and keep findings that are implementation-verified, not covered by existing evidence, and not dropped by the parity/deduplication filters.
       If a candidate is not yet implementation-verified because verification was unsafe, mutating, or required a shared/exclusive resource, carry its `verification_needed` in the ledger instead of dropping it.
     - PR modes: apply `pr_common.md` Deduplication + Truth Filter, Existing Pending Review Reconciliation, CI Coverage Gate, and PR Necessity + Correctly-Open Audit classifications
     - local-changes mode: do not apply PR-thread deduplication or PR CI coverage exemptions;
       judge against the staged/unstaged/range scope in the packet
   - Judge fresh-eyes clarity candidates with full context, with one guard: a PR body, commit message, or thread that explains the confusing code does not refute the finding — the lane's premise is that the code alone failed to carry that context.
     Use the context to choose the fix (why-comment, rename, extraction), not to drop the finding. Clarity findings cap at MEDIUM.
   - For PR modes, read any current-account pending review and already-submitted current-account review comments/replies before drafting payloads.
     Merge kept pending findings with kept new findings into one final draft; drop stale pending findings with evidence;
     block rather than producing competing or contradictory payloads.
   - For kept UI findings that may become human-visible review feedback, require valid screenshot handoff entries before drafting.
     Verify screenshot paths when possible and surface them only in final `UI evidence attachments:`.
     If screenshot handoff is missing, rerun `live-ui-review` or block with the exact reason;
     do not draft a UI-related comment from text-only UI evidence.
     Never upload images, put local paths in GitHub review bodies, or create extra comments just to carry image paths.
   - Drop only with source/API/runtime evidence for one of these hard reasons:
     - unsupported claims
     - unreachable-path findings
     - PR-mode findings covered by verified PR CI or existing PR artifacts
     - candidates classified as `preserved_limitation` or `prose_drift` by the Replacement/Migration Parity Gate
     - candidates refuted by the adversarial verifier, after the controller checks the refutation's source/API/runtime evidence addresses the candidate's actual claim
     - findings that only a worker asserted without evidence and without a decisive `verification_needed` path
     - PR necessity claims that rely only on ambient precedent without proving the current PR's actual diff and directly referenced artifacts
   - A findings-auditor drop recommendation or an adversarial-verifier verdict is advisory.
     The controller must name the hard drop reason and evidence; otherwise keep the finding, merge it with a duplicate, run the needed verification, or block with explicit uncertainty.
   - For every verification-ledger item, record one disposition:
     - `resolved`: evidence makes it irrelevant or answers the fork,
     - `run`: the controller ran the serial non-mutating/heavy check,
     - `blocked`: the check is unsafe, out of scope, or impossible, with exact blocker,
     - `not needed`: the item cannot affect keep/drop/action, with evidence.
   - When running serial verification, apply the `shared_rules.md` Read-Only Probes search discipline:
     prefer native search/listing tools for first-pass broad searches, and use shell `rg` only with a path, glob, or exact-symbol scope.
   - A `verification_needed` that can flip a kept/dropped finding, fix decision, or draft payload is blocking until it is `resolved` or `run`.
     Do not let findings audit or stale PR-intent assumptions convert it to `not needed`.
8. **Act only after judgment.**
   Branch strictly on `fix_authorized` and the mode recorded in step 1; never infer fix authorization from the fact that the change is merely checked out locally (a locally-checked-out other-authored branch with no assignee/takeover signal is still `fix_authorized: no`).
   - Do not act while a blocking verification-ledger item or intent dependency remains unresolved.
     Either resolve it first, or stop/draft with explicit remaining uncertainty according to the mode.
   - Before composing any human-visible text in this step — review summaries, draft comments/suggestions, thread replies, or PR-level feedback — load `~/.agents/skills/k-communication/SKILL.md` via the Skill tool and word the text to its contract.
     This is a blocking `Use when` match (you are drafting content another human will read), not an optional pointer;
     do the load even when no fix is applied and even when the only output is a single review comment.
     If a verified domain overlay applies to the target repo/org (e.g. `~/.agents/skills/k-elastic-domain/SKILL.md` for `elastic/kibana`), load it too for repo-specific wording/footer rules before drafting.
   - `fix_authorized: yes` (own / assigned / adopted PR, or local-changes self flow):
     - apply the selected fixes in the working tree; no separate "fix" keyword is required
     - then run the step-10 post-act verification phase (an adopted/assigned PR is a change-producing flow;
       do not skip the fix-diff Post-Review Stage just because the PR was originally other-authored)
     - for PR-fix/thread modes, still draft thread replies/suggestions per `pr_fix.md` for anything not fixed in code;
       human-visible publishing (commit/push/post/resolve) stays on its own explicit-approval gate
   - `fix_authorized: no` (`authorship: other`/`unknown`, no assignee/takeover signal):
     - draft public-ready comments/suggestions only
     - do not edit code
     - do not run fixes
     - do not post
9. **Post-act verification (only when the working tree was edited this flow).**
   This phase is mandatory after any applied fix in step 9, including self-review and adopted/assigned PR takeovers.
   Do not declare the change done, and do not treat the final summary as a substitute for this phase.
   Because the working tree was edited, `fix_authorized` is `yes`, which carries full verification-mutation permission:
   bootstrap/install (`yarn kbn bootstrap` and equivalents), code generation, SCSI, `/tmp` repros, and re-running gates are all in-bounds here.
   Run a fix -> verify -> fix -> verify loop until the gates are green or a genuine blocker remains.
   - **Quality gates — make them runnable, then run; loop, don't defer.**
     Discover the repo's lint / type_check / test commands from repo sources (do not guess), prefer scoped/targeted commands for the affected package, and run them over the fix.
     - If the gates cannot run yet because the environment is not prepared (e.g. repo not bootstrapped, deps not installed):
       prepare it (run `yarn kbn bootstrap` / the repo's install/setup) and then run the gates.
       Not-yet-bootstrapped is a setup step to perform, not a reason to stop, because the flow is fix-authorized.
     - If a gate fails or types get worse: fix it in the working tree and re-run (the fix -> verify loop), do not stop at the first red gate.
     - Only treat it as a blocking stop-and-ask when setup itself fails or is impossible (bootstrap errors out, toolchain genuinely unavailable in this environment, or commands are undiscoverable after inspecting repo sources): then state exactly what failed, the evidence, and the exact command(s) for the user.
       Never fold an un-run gate into a closing summary as if verification were complete.
   - **Fix-diff Post-Review Stage (the four dimensions).**
     Run the Post-Review Stage in `~/.agents/skills/k-review/references/judging_core.md` with the **fix diff** as the subject (this flow's `git diff` / staged set / commit range), never the original PR diff.
     This is the controller's own work; the pre-action findings audit in step 6 audits candidate findings and does NOT replace it.
     Apply the four canonical dimensions by name — redundancy, verbosity, semantic + logical duplication, gaps —
     anchor each finding in an exact location, resolve each in the working tree, and re-run the quality gates if the cleanup touched code.
   - **Resolve carried `verification_needed`.**
     For every `verification_needed` kept through judgment, make and report a per-item decision:
     either run the serial non-mutating/heavy check now, or explicitly carry it as a stated blocker with the reason it was not run.
     Do not leave a kept `verification_needed` in an undecided state.
   - Report this phase in the Output `Post-act verification:` line: gates run/blocked (with command evidence or the exact blocker), fix-diff Post-Review Stage result per dimension (clean or what was cleaned), and each `verification_needed` decision.

## Premise corrections and completion gate

If the user supplies new context that changes the target, intent, accepted behavior, or relevant artifacts after `/agent-review` has started or after it has produced a conclusion, rebuild the scope packet and restart from the earliest invalidated phase.
If the controller intentionally leaves `/agent-review` mode for direct verification/editing, state that downgrade explicitly before making edits and do not reuse the stale agent-review judgment as if the flow remained complete.

Do not declare `/agent-review` complete while any decisive verification-ledger item, intent dependency, pending-review reconciliation blocker, required live-UI trigger without a valid blocker, or post-act verification item is unresolved.
The final output may report blockers or remaining uncertainty, but it must not present the flow as completed when an unresolved item can change the action or verdict.

## PR necessity audit

`pr-necessity-auditor` is the blocking PR-mode/intent worker from orchestration step 2:
evidence-only, never decides, posts, resolves, edits, commits, or pushes.
Orchestration step 2 owns when it runs and how its result gates reviewer fan-out.
Full audit scope (author intent, correctly-open checks, duplicate/superseding-work search) and hard constraints live in `~/.agents/skills/k-agent-review/references/pr-necessity-auditor.md`.

## Live UI review

`live-ui-review` is the conditional UI/runtime verifier from orchestration step 5:
applicability trigger, mode boundary, target-packet selection, worktree identity, and required runtime config are owned there.
Full worker-facing procedure lives in `~/.agents/skills/k-agent-review/references/live-ui-review.md`, which loads the shared runtime contract `~/.agents/skills/k-agent-review/references/live-ui-runtime.md` (preflight, readiness stability guard, runtime-start rung, data/setup ladder, hard runtime constraints); `live-ui-review.md` adds the base-vs-head Playwriter comparison and the exact return shape.

Controller validation: reject and rerun any `live-ui-review` result that:

- does not match the selected target packet
- uses the controller cwd or base/main runtime as the PR/head target for an explicit PR/branch review without proving that checkout is on the reviewed PR/head branch/sha
- reports only generic localhost probing when the packet requires named targets
- omits a required target from the selected packet
- uses WebFetch or shell/HTTP probes as readiness evidence
- skips Playwriter target checks
- claims targets are unavailable without showing the selected target/preflight evidence
- uses browser/route/network mocks for a data-dependent UI finding without first attempting or explicitly ruling out faithful local/dev data setup from the selected target packet
- uses browser/route/network mocks when faithful verification is blocked by a required runtime environment change;
  that must be returned as `Blocked` with setup instructions instead
- returns `Blocked` for a missing/un-started local runtime in a shell-capable harness when the selected target packet documents a start command (the runtime-start rung); the worker should start it and continue, so rerun after the runtime is started
- lists screenshot artifacts without local paths, descriptions, target URL/branch, linked candidate/finding placement, suggested manual attachment placement, folder-open/provided status, or fidelity/cleanup notes
- returns applicable UI comparison evidence for a finding that may become draft review feedback with `ui_evidence_artifacts: none` and no valid blocker/non-applicability result
- omits applicability, exact URLs checked, Playwriter preflight status, readiness result for each target, branch/runtime evidence, comparison evidence for each checked candidate, UI evidence artifact manifest or `none`, page cleanup/owned-page URLs, and blockers/uncertainty
- omits the selected `target_packet` source, including overlay source when an overlay supplied the packet

Do not reject or rerun a result that reports a valid Playwriter harness blocker:

- read-only/Ask-mode blocked `playwriter skill` or Playwriter commands
- every selected exact browser/runtime target URL was attempted or explicitly blocked before navigation
- repeated reload/same-URL/same-snapshot loop was detected within the readiness stability guard

## Output

Return:

- `Base context:` line from the review methodology.
- Worker selection summary for each delegated phase, including any fallback reason.
- Reviewer roster: the angle lanes launched and the scope-level evidence for each selection.
- Adversarial verification: families used (`<session-family> vs <verifier-family>` or `same (degraded)`), verdict counts (confirmed/refuted/undecidable), or `skipped (no candidates)`.
- PR necessity audit summary: report greenlight, merge-readiness/status blockers or uncertainty, skipped-with-reason, or blocker status.
- Investigation summary: what each reviewer found (fresh-eyes lane included, or its skip reason), what the live UI reviewer found, and what the findings audit found, including whether the audit was inline or delegated.
- Serial verification: any `verification_needed` returned by reviewer lanes and whether the controller ran, skipped, or blocked on it.
- Intent dependency audit: resolved / not applicable / blocked, with evidence.
- Verification ledger: every `verification_needed` or blocker that affected keep/drop/action and its disposition.
- Controller judgment: findings kept/dropped and why.
- Pending review reconciliation: none found, reused existing, merged replacement needed, stale pending dropped, or blocked with reason.
- Action taken or draft payloads, depending on mode.
- Post-act verification: for any flow that edited the working tree, report quality gates (run with command evidence, or blocked with the exact blocker and the command the user must run), the fix-diff Post-Review Stage result per dimension (redundancy, verbosity, semantic + logical duplication, gaps), and each carried `verification_needed` run/blocked decision.
  Omit only when no working-tree edit occurred.
- UI evidence attachments: for kept UI findings, local screenshot artifact paths with descriptions, target URL/branch, suggested manual attachment placement, and folder-open/provided status.
  Use `none` only when no kept UI finding needs draft feedback, or when a valid blocker/non-applicability result explains why no screenshot exists.
  Keep this separate from GitHub review bodies because local paths are only for the user.
- Remaining uncertainty or gated side effects.
- Completion gate: clear, or blocked with the unresolved item.
- `Compatibility impact: none | removed (requested) | kept existing (requested)`.
