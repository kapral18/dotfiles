---
name: k-deep-review
description: "Manual-only controller contract for /k-deep-review deep-review fan-out, findings aggregation, and gated fixes/comments."
disable-model-invocation: true
---

# Deep Review

This is the controller contract for `/k-deep-review`.

The controller:

- routes
- delegates
- aggregates
- judges
- performs gated side effects

The substantive review work happens in isolated reviewer workers that load the shared `k-review` skill themselves.
Two exceptions: the blind fresh-eyes clarity lane loads only `k-review/references/fresh-eyes.md`, and the adversarial verifier loads `judging_core.md` and its required conditional references through `k-review/references/adversarial-verifier.md`.

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
If a finding needs shared-state mutation, a shared service, or another exclusive resource to verify, return the verification need to the controller instead of running that verification inside any parallel lane.

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
- running the conditional blocking `k-agent-pr-necessity-auditor` before implementation review
  - applies to other-authored/unknown PRs
  - applies to local flows with a PR-intent dependency
- materializing the read-only review context pack before reviewer fan-out and putting the pack path plus manifest `head_sha` in every scope packet
- launching the reviewer workers after any required PR necessity greenlight: the angle lanes plus the conditional blind fresh-eyes clarity lane
- running conditional `k-agent-live-ui-review` verification after lane merge/dedup, before the findings audit
  - applies when changed paths or merged candidate findings touch UI/runtime behavior
  - requires applicable runtime evidence
  - requires screenshot handoff evidence for any UI-related finding that may become draft review feedback, unless live UI returns a valid blocker or non-applicability result
- running the controller findings audit phase after live UI returns evidence/non-applicability/blocker or is explicitly skipped;
  delegate to `k-agent-findings-auditor` only when a findings-audit delegation condition is true
- running the final adversarial verification pass (cross-family preferred at equal capability, SOP §3.7) over the audited candidate set
- aggregating worker outputs, `k-agent-pr-necessity-auditor` status, reviewer findings, live UI status/evidence/artifacts/skip reason, audit output, and final adversarial verification verdicts
- deciding which worker-reported `verification_needed` items deserve serial controller verification
- judging kept/dropped findings after aggregation
- reconciling PR-mode draft payloads before preparing or posting final review feedback
  - compare against existing current-account pending reviews, submitted review comments, and replies
- applying fixes, drafting payloads, or touching GitHub only after the relevant `k-review`/`communication`/`github`/`git` gates
  - load `k-communication` before wording any human-visible draft

Before fan-out, the controller must not load or run the full `k-review` skill.

That one section:

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

Leave the coverage checklist, base-context investigation, and worker review analysis to the reviewer workers;
the controller runs them once at most, in their owning phase.

Reviewer workers own the full investigation methodology.

- Role-specific runtime contracts live under `~/.agents/skills/k-review/references/`.
- A reviewer lane loads only:
  - `~/.agents/skills/k-review/references/reviewer-worker.md`
  - `~/.agents/skills/k-review/references/judging_core.md`
  - the conditional references that `judging_core.md` requires for the assigned review scope/checks
  - `~/.agents/skills/k-review/references/context-pack.md`, when the scope packet names a pack
  - the lens skill named by its pasted lane entry, when that entry names one
- Lanes deliberately do not load `k-review/SKILL.md`, `shared_rules.md`, `pr_common.md`, `lanes.md`, or a mode file.
  Those carry routing, drafting, posting, verdict, and pending-review reconciliation rules only the controller may act on, and they roughly double a lane's context for instructions it is forbidden to use.
  Anything a lane genuinely needs from them belongs in its scope packet, which the controller owns.
- Return only evidence, candidate findings, and any `verification_needed` entries that were unsafe or required shared-state mutation/contention inside a parallel lane.
- Workers investigate only; the controller alone edits, posts, resolves, commits, pushes, and decides what should be fixed/commented on.
- The blind fresh-eyes lane is a further exception: it loads only `~/.agents/skills/k-review/references/fresh-eyes.md`, staying blind to the `k-review` skill and all PR context.

The active harness owns subagent discovery and invocation.

- Read `~/.agents/skills/k-review/references/runtime-harnesses.md` only for capability caveats.
- Never invent a custom-agent layer the harness does not expose.

## Default orchestration

Load phase procedures at their owning phase.
Before entering or resuming a phase, read its required reference in full; do not execute from its summary alone.
Record current phase, completed gates, unresolved obligations, and evidence pointers in the existing review identity/lane ledger.
After compaction or handoff, read the ledger and current phase reference; do not replay completed phases unless the premise-correction gate invalidates them.

The phase order is strict:

1. route and scope
2. blocking PR necessity/intent gate, only when the mode and authorship resolved in step 1 trigger it
3. the reviewer lane roster (one sighted baseline lane plus evidence-triggered angle/fresh-eyes lanes, launched in parallel when more than one lane applies)
4. lane merge/dedup plus conditional live UI verification over the merged candidate set
5. findings audit, inline or delegated by the findings-audit delegation conditions
6. final adversarial verification (cross-family preferred at equal capability, SOP §3.7) over the audited candidate set
7. controller aggregation, judgment, PR-mode pending-review reconciliation, and action
8. post-act verification, only for any flow that edited the working tree (gates + fix-diff Post-Review Stage)

Start a later phase only after the current phase returns; the final adversarial verifier is the last investigation subagent before controller judgment/action.
In blocking phases, wait for completion notifications or use the harness's synchronous/blocking mechanism instead of polling background workers with long waits just to check status.
If the harness cannot await background workers by id (for example Cursor), apply `runtime-harnesses.md`;
launch the worker as the harness's real background subagent, then wait only through a harness-native subagent completion signal.
Never loop blind fixed-interval sleeps waiting on a subagent.
The same rule applies after `write_agent` follow-ups for addenda or reconciliation checks:
send the follow-up, state that the phase is waiting only when there is observable worker progress, and end the turn unless the worker has already completed.
The controller may read completed phase outputs, but it must not perform later-phase analysis while the current phase is still running.

### Worker lifecycle and progress truth

A `write_agent` delivery acknowledgment is not progress.
Never narrate a background worker as running, working, or testing unless there is observable evidence:
artifact paths appearing, relevant processes still running, or a `read_agent` turn with content.
If a worker turn returns a request-too-large/context-overflow error, or `read_agent` shows an empty response turn with no artifacts or processes, treat that worker context as dead.
Do not retry into it. Respawn a fresh worker with a tight self-contained packet or take over inline.
Environment-heavy workers restart their environment on each turn anyway, so a fresh worker loses no useful runtime continuity.
After three follow-up tasks to the same background worker, prefer respawn-fresh over further reuse unless the worker has a measured continuity need and still has observable progress.
Any numeric or behavioral claim sourced from worker prose is a self-report, not evidence.
Independently verify it with artifact timestamps, logs, or a rerun before it appears in human-visible review text.

Before every launch, record the lane in the review identity and lane ledger (`shared_rules.md`, Review Persistence) as `state=launched`, and re-read that ledger first: a lane it already shows as `launched` is awaited, never relaunched.
After a context summary the ledger, not recall, says what is running.

For every delegated worker, emit an export-visible worker selection line before launch:

```text
Worker selection: phase=<pr-necessity|review:<angle>|fresh-eyes|adversarial-verify|live-ui|findings-audit>, profile=<configured profile name>, agent_type=<task/subagent agent type>, model_required=<model-or-n/a>, model_used=<model-or-n/a>, model_status=<exact|unavailable|n/a>, tool_readonly=<false|n/a>, launch_wait=<blocking|background|n/a>, invocation=<named|fallback>, fallback_reason=<none or reason>
```

This line is part of the audit trail.
If a runtime export hides task arguments, the worker selection line must still prove whether the controller used named profiles.
It must also show any fallback such as `general-purpose`.
A worker launch is invalid when `model_required` differs from `model_used` or `model_status` is not `exact`, unless the phase is explicitly `n/a` for model selection.
The fresh-eyes phase is not `n/a`: named fresh-eyes profiles and generic fresh-eyes launches both use the resolved lane model, and worker selection must prove that exact value.

1. **Route and scope.**

Before route/scope discovery or rebuilding its packet, load and follow this complete phase procedure.
Required reference: `~/.agents/skills/k-deep-review/references/route-scope.md`.

1. **Run conditional blocking PR necessity/intent audit.**

Before deciding whether this gate applies, skipping it, or launching its auditor, load and follow this complete phase procedure.
Required reference: `~/.agents/skills/k-deep-review/references/pr-necessity.md`.

1. **Launch the reviewer lane roster.**

Before selecting or launching reviewer lanes, load and follow this complete phase procedure, including the fresh-eyes trigger and launch barrier.
Required reference: `~/.agents/skills/k-deep-review/references/reviewer-roster.md`.

1. **Merge candidates and run conditional live UI verification.**
   - After every launched reviewer lane returns, collapse same-root-cause/same-anchor duplicates into one merged candidate each (merge/dedup only; no new controller investigation).
   - If the merged set is empty, skip live UI, findings audit, and final adversarial verification;
     report the skip reason and continue to action/output with no findings.
   - Immediately after lane merge/dedup, and after the blocking PR necessity gate has passed when it applies, apply a read-only controller parity filter to replacement/test-migration candidates:
     - apply the Replacement/Migration Parity Gate from `judging_core.md` to replacement/test-migration candidates
     - drop candidates classified as `preserved_limitation` or `prose_drift`
     - do not treat test-only UI code as live-UI applicability by itself
   - Launch `k-agent-live-ui-review` when changed paths or any merged candidate touch UI/runtime behavior and runtime evidence is applicable.
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
   - Use those permissions only for the lane's permitted verification tools: read-only shell/git/`gh` for investigation workers, or Playwriter commands for `k-agent-live-ui-review`.
     `k-agent-live-ui-review` may also run explicit local/dev runtime data setup against verified targets.
   - Mode boundary: default `k-agent-live-ui-review` is verification-only.
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
   - Resolve required runtime config once, before the first `k-agent-live-ui-review` launch:
     from the changed paths and kept candidates, determine any runtime/feature-flag settings the path under review needs to be reachable.
     Pass them to the worker so the runtime is started correctly the first time instead of started default and reconfigured after a blocker.
     The concrete settings and the start-time mechanism are owned by the selected target packet.
     For example, the Kibana overlay owns `required_kbn_flags` -> `,kbn-stack -K`;
     keep specific flag names and values in the packet/overlay, not here. When none are needed, pass an empty set.
   - Include the selected target/preflight packet and the resolved required runtime config in the worker prompt so the worker starts with it instead of rediscovering it.
   - Windows/VirtualBox coverage is out of scope for this flow: `k-agent-live-ui-review` verifies the local browser only.
     When the user explicitly wants Windows/VirtualBox coverage too, add the manual `~/.agents/skills/k-live-ui-windows/SKILL.md` skill to this turn's work by hand; never infer it from PR/issue context.
   - It returns one of:
     - `Not applicable`
     - comparison evidence with `ui_evidence_artifacts`
     - target/branch/runtime/data blocker for the controller to surface
   - For an applicable UI-related candidate that may become draft review feedback, screenshots are required supporting evidence.
     If `k-agent-live-ui-review` confirms or materially supports the candidate without screenshot handoff entries, rerun the worker or carry a blocker; draft the comment only with screenshot-backed UI evidence.
   - Rerun a blocked live-UI result automatically only for a missing/un-started local runtime in a shell-capable harness when the selected target packet documents a start command.
     That case is the runtime-start rung, not a terminal blocker; have the runtime started and rerun rather than surfacing it as remaining uncertainty.
   - A read-only/Ask-mode Playwriter block is a valid blocker to surface.

2. **Run controller findings audit on candidate findings.**

Before choosing inline versus delegated audit or auditing findings, load and follow this complete phase procedure.
Required reference: `~/.agents/skills/k-deep-review/references/findings-audit.md`.

1. **Run final adversarial verification.**

Before deciding whether to skip or launch final adversarial verification, load and follow this complete phase procedure, including its miss-sweep audit.
Required reference: `~/.agents/skills/k-deep-review/references/adversarial-verification.md`.

1. **Aggregate and judge in the controller.**

Before aggregation, keep/drop judgment, serial verification, or pending-review reconciliation, load and follow this complete phase procedure.
Required reference: `~/.agents/skills/k-deep-review/references/judgment.md`.

1. **Act only after judgment.**
   Branch strictly on `fix_authorized` and the mode recorded in step 1; fix authorization comes only from that recorded value, since a locally-checked-out other-authored branch with no assignee/takeover signal is still `fix_authorized: no`.
   - Act only after every blocking verification-ledger item and intent dependency is resolved.
     Either resolve it first, or stop/draft with explicit remaining uncertainty according to the mode.
   - Before composing any human-visible text in this step — review summaries, draft comments/suggestions, thread replies, or PR-level feedback — load `~/.agents/skills/k-communication/SKILL.md` via the Skill tool and word the text to its contract.
     This is a blocking `Use when` match (you are drafting content another human will read), not an optional pointer;
     do the load even when no fix is applied and even when the only output is a single review comment.
     If a verified domain overlay applies to the target repo/org (e.g. `~/.agents/skills/k-elastic-domain/SKILL.md` for `elastic/kibana`), load it too for repo-specific wording/footer rules before drafting.
   - `fix_authorized: yes` (own / assigned / adopted PR, or local-changes self flow):
     - apply the selected fixes in the working tree; no separate "fix" keyword is required
     - then run the post-act verification phase (an adopted/assigned PR is a change-producing flow;
       do not skip the fix-diff Post-Review Stage just because the PR was originally other-authored)
     - for PR-fix/thread modes, still draft thread replies/suggestions per `pr_fix.md` for anything not fixed in code;
       human-visible publishing (commit/push/post/resolve) stays on its own explicit-approval gate
   - `fix_authorized: no` (`authorship: other`/`unknown`, no assignee/takeover signal):
     - draft public-ready comments/suggestions only: no code edits, no fixes run, no posting
2. **Post-act verification (only when the working tree was edited this flow).**
   This phase is mandatory after any applied fix from the Act step, including self-review and adopted/assigned PR takeovers.
   Do not declare the change done, and do not treat the final summary as a substitute for this phase.
   Because the working tree was edited, `fix_authorized` is `yes`, which carries full verification-mutation permission:
   bootstrap/install (`yarn kbn bootstrap` and equivalents), code generation, SCSI, `/tmp` repros, and re-running gates are all in-bounds here.
   Run a fix -> verify -> fix -> verify loop until the gates are green or a genuine blocker remains.
   - **Quality gates — make them runnable, then run; loop, don't defer.**
     Discover the repo's lint / type_check / test commands from repo sources (repo sources are the only valid source;
     guessing is out), prefer scoped/targeted commands for the affected package, and run them over the fix.
     - If the gates cannot run yet because the environment is not prepared (e.g. repo not bootstrapped, deps not installed):
       prepare it (run `yarn kbn bootstrap` / the repo's install/setup) and then run the gates.
       Not-yet-bootstrapped is a setup step to perform, not a reason to stop, because the flow is fix-authorized.
     - If a gate fails or types get worse: fix it in the working tree and re-run (the fix -> verify loop), do not stop at the first red gate.
     - Only treat it as a blocking stop-and-ask when setup itself fails or is impossible (bootstrap errors out, toolchain genuinely unavailable in this environment, or commands are undiscoverable after inspecting repo sources): then state exactly what failed, the evidence, and the exact command(s) for the user.
       Never fold an un-run gate into a closing summary as if verification were complete.
   - **Fix-diff Post-Review Stage (the four dimensions).**
     Run the Post-Review Stage in `~/.agents/skills/k-review/references/judging_pipeline.md` with the **fix diff** as the subject (this flow's `git diff` / staged set / commit range), never the original PR diff.
     This is the controller's own work; the pre-action controller findings audit phase audits candidate findings and does NOT replace it.
     Apply the four canonical dimensions by name — redundancy, verbosity, semantic + logical duplication, gaps —
     anchor each finding in an exact location, resolve each in the working tree, and re-run the quality gates if the cleanup touched code.
   - **Resolve carried `verification_needed`.**
     For every `verification_needed` kept through judgment, make and report a per-item decision:
     either run the serial non-mutating/heavy check now, or explicitly carry it as a stated blocker with the reason it was not run.
     Do not leave a kept `verification_needed` in an undecided state.
   - Report this phase in the Output `Post-act verification:` line: gates run/blocked (with command evidence or the exact blocker), fix-diff Post-Review Stage result per dimension (clean or what was cleaned), and each `verification_needed` decision.

## Premise corrections and completion gate

If the user supplies new context that changes the target, intent, accepted behavior, or relevant artifacts after `/k-deep-review` has started or after it has produced a conclusion, rebuild the scope packet and restart from the earliest invalidated phase.
If the controller intentionally leaves `/k-deep-review` mode for direct verification/editing, state that downgrade explicitly before making edits and do not reuse the stale deep-review judgment as if the flow remained complete.

Declare `/k-deep-review` complete only when every decisive verification-ledger item, intent dependency, pending-review reconciliation blocker, required live-UI trigger, and post-act verification item is resolved or carries a valid blocker.
The final output may report blockers or remaining uncertainty, but it presents the flow as completed only when no unresolved item can change the action or verdict.

## PR necessity audit

`k-agent-pr-necessity-auditor` is the blocking PR-mode/intent worker from orchestration step 2: evidence-only:
it decides, posts, resolves, edits, commits, and pushes nothing.
Orchestration step 2 owns when it runs and how its result gates reviewer fan-out.
Full audit scope (author intent, correctly-open checks, duplicate/superseding-work search) and hard constraints live in `~/.agents/skills/k-review/references/pr-necessity-auditor.md`.

## Live UI review

Before accepting, rejecting, or rerunning a live-UI worker result, load and follow this complete result-validation procedure.
Required reference: `~/.agents/skills/k-deep-review/references/live-ui-validation.md`.

## Output

Return:

- `Base context:` line from the review methodology.
- Worker selection summary for each delegated phase, including any fallback reason.
- Reviewer roster: the lanes launched, the scope-level evidence for each selection, and any lenses folded into another lane.
- Lane yield: for each launched lane, `candidates returned -> findings kept after judgment`, plus the shared suites the controller ran once for all lanes.
  A lane that returned nothing kept is not a failure, but it is the evidence for dropping that trigger next time —
  report it plainly rather than hiding it in the investigation summary.
- Adversarial verification: families used (`<session-family> vs <verifier-family>` or `same (degraded)`), verdict counts (confirmed/refuted/undecidable), or `skipped (no candidates)`.
- Miss sweep: `new-candidate` count returned by the verifier, how many survived the inline re-audit, or `none above the bar`.
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
- UI evidence attachments: for kept UI findings, local screenshot artifact paths with descriptions, target URL/branch, and suggested embedding placement.
  Use `none` only when no kept UI finding needs draft feedback, or when a valid blocker/non-applicability result explains why no screenshot exists.
  Keep this separate from GitHub review bodies because local paths are only for the upload step.
- Closeout memory: persist verified reusable insights via `,ai-kb remember` and record correction-class lessons via `,agent-memory note anti_pattern`; write only verified, durable items.
- Remaining uncertainty or gated side effects.
- Completion gate: clear, or blocked with the unresolved item.
- `Compatibility impact: none | removed (requested) | kept existing (requested)`.
