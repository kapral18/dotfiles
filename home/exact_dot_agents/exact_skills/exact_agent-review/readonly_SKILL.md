---
name: agent-review
description: Agentic review orchestration that reuses the review skill's methodology without mutating it. Use when the user invokes /agent-review, asks for multi-agent review orchestration, or wants reviewer subagents plus finding aggregation before any fixes/comments.
---

# Agent Review

This is the controller contract for `/agent-review`.

The controller:

- routes
- delegates
- aggregates
- judges
- performs gated side effects

The substantive review work happens in isolated reviewer workers that load the shared `review` skill themselves.

The reviewer-worker lanes are read-only:

- no working-tree edits
- no shared-state mutations or state-changing verification commands
- no live-UI checks
- no posting or resolving
- no commits or pushes
- no fix application

Workers may run non-mutating verification at whatever depth is needed to find and validate review findings. Parallel lanes must not mutate the working tree, repo-local caches, databases, dev services, browser state, GitHub, git state, or other shared runtime state. Use unique `/tmp` paths or isolated copies for disposable reproduction artifacts. Do not skip useful verification only because it is expensive or another lane may also run it. If a finding needs shared-state mutation, a shared service, or another exclusive resource to verify, return the verification need to the controller instead of doing it inside both lanes.

Workers only investigate and return candidate findings or `verification_needed`.

All side effects happen later in the controller, gated by the final act phase.

The `review` skill and its references remain the source-of-truth methodology workers load read-only.

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
- running the conditional blocking `pr-necessity-auditor` for other-authored or unknown PRs before implementation review
- launching the two reviewer workers after any required PR necessity greenlight
- running conditional `live-ui-review` verification after reviewer workers finish
- running the findings audit phase after live UI returns evidence, non-applicability, or a target/branch/unsafe-data-setup blocker; delegate to `findings-auditor` only when proportional
- aggregating worker outputs, `pr-necessity-auditor` evidence or skip/blocker status, `live-ui-review` evidence or skip/target-branch-data blocker status, and audit output
- deciding which worker-reported `verification_needed` items deserve serial controller verification
- judging kept/dropped findings after aggregation
- reconciling PR-mode draft payloads with existing current-account pending reviews, submitted review comments, and replies before preparing or posting final review feedback
- applying fixes, drafting payloads, or touching GitHub only after the relevant `review`/`github`/`git` gates

Before fan-out, the controller must not load or run the full `review` skill.

It may load only one router section first:

- Resolve `authorship` using the review router's Role Detection procedure (`~/.agents/skills/review/SKILL.md`).
- Do this before any worker launch because the PR necessity gate and final act phase depend on that value.
- Do not infer authorship from the change being checked out locally.
- A branch tracking another person's fork is `other`.
- Commits authored by someone else are `other`.
- If authorship cannot be verified, it is `unknown`.

After workers return, the controller may consult only the minimum relevant review references for:

- deduplication
- severity
- side-effect gates
- `~/.agents/skills/review/references/pr_common.md` for PR-mode reconciliation
- `~/.agents/skills/review/references/shared_rules.md` for existing pending-review awareness

Do not rerun the coverage checklist, base-context investigation, or worker review analysis.

Reviewer workers own the full investigation methodology.

- Shared runtime contract: `~/.agents/skills/agent-review/references/runtime-contracts.md`.
- Load inside each worker context:
  - `~/.agents/skills/review/SKILL.md`
  - `~/.agents/skills/review/references/judging_core.md`
  - `~/.agents/skills/review/references/shared_rules.md`
  - selected mode file under `~/.agents/skills/review/references/`
  - `~/.agents/skills/review/references/pr_common.md` for PR modes
- Return only evidence, candidate findings, and any `verification_needed` entries that were unsafe or required shared-state mutation/contention inside a parallel lane.
- Never edit, post, resolve, commit, push, or decide what should be fixed/commented on.

The active harness owns subagent discovery and invocation.

- Read `~/.agents/skills/agent-review/references/runtime-harnesses.md` only for capability caveats.
- Never invent a custom-agent layer the harness does not expose.

## Default orchestration

The phase order is strict:

1. route and scope
2. blocking PR necessity gate, only for other-authored or unknown-author PRs
3. two concurrency-safe reviewer workers in parallel
4. live UI verification when applicable
5. findings audit, inline or delegated by proportional-depth rules
6. controller aggregation, judgment, PR-mode pending-review reconciliation, and action

Do not start a later phase until the current phase returns. In blocking phases, do not poll background workers with long waits just to check status; wait for completion notifications or use the harness's synchronous/blocking mechanism. The controller may read completed phase outputs, but it must not perform later-phase analysis while the current phase is still running.

For every delegated worker, emit an export-visible worker selection line before launch:

```text
Worker selection: phase=<pr-necessity|review-gpt|review-opus|live-ui|findings-audit>, profile=<configured profile name>, agent_type=<task/subagent agent type>, model=<model>, invocation=<named|fallback>, fallback_reason=<none or reason>
```

This line is part of the audit trail. If a runtime export hides task arguments, the worker selection line must still prove whether the controller used named profiles or a fallback such as `general-purpose`.

1. **Route and scope.** Build a scope packet with:
   - mode: `local_changes.md`, `pr_review.md`, or `pr_fix.md`
   - `authorship`: `self`, `other`, or `unknown`
   - PR number or diff range
   - base branch
   - staged/unstaged state
   - thread IDs
   - user constraints
   - expected output shape

   Resolve `authorship` via the review router's Role Detection. Do not duplicate worker review analysis in the controller.

2. **Run conditional blocking PR necessity audit.**
   - Run `pr-necessity-auditor` before any implementation reviewer when:
     - mode is `pr_review.md` or `pr_fix.md`, and
     - `authorship` is `other` or `unknown`.
   - Invoking `/agent-review` is the request for this PR meta-audit; do not require a second user opt-in.
   - Skip it for local changes and self-authored PRs.
   - This worker is read-only and evidence-only.
   - Give it the scope packet plus the PR URL/number, base/head refs, changed paths, directly referenced issues/PRs, and any already-known user constraints.
   - It must follow the `PR necessity auditor` section in `runtime-contracts.md`.
   - It returns one of:
     - `Not applicable`
     - greenlight evidence that the PR is sensible enough to review further
     - blocker or stop status for inaccessible GitHub, Slack, history, unclear intent, not-needed/superseded work, or incorrectly-open status
   - Greenlight means there is no unresolved blocker and no supported classification that makes implementation review premature or unnecessary. For other-authored or unknown-author PRs, continue to reviewer fan-out only when the audit supports `needed: yes` and no material correctly-open/intent concern blocks review.
   - Greenlight is not merge readiness. Failed/missing labels, outdated-branch checks, unknown mergeability, or other status blockers may be surfaced as `merge_readiness`/status uncertainty while still allowing implementation review to continue.
   - Never treat `mergeable: UNKNOWN`, `mergeStateStatus: UNKNOWN`, or missing merge metadata as proof of no conflicts. Record it as unknown.
   - If the audit returns blocked, unclear, not needed, superseded, or incorrectly open, stop the implementation review flow and surface the supported blocker/PR-level draft feedback. Do not launch reviewer workers, live UI, or findings audit unless the user explicitly asks to continue anyway.
   - Do not rely on the auditor to decide or post. The controller judges and gates any draft feedback.

3. **Launch two code investigation reviewers in parallel.**
   - Emit both reviewer launches in one message (a single tool-call batch).
   - Use the current harness's native configured reviewer workers or task mechanism.
   - Copilot CLI: launch the named worker profiles (`review-gpt-5-5-extra-high`, `review-opus-4-8-xhigh-non-thinking`, `pr-necessity-auditor`, `live-ui-review`, `findings-auditor`) as task agent types. They are model-invocable but not user-invocable. Do not use `general-purpose` unless a named launch is proven unavailable in the active Copilot runtime, and state that fallback reason.
   - Cursor model selection is explicit, never inherited:
     - GPT/default lane: `gpt-5.5-extra-high`
     - Opus lane: `claude-opus-4-8-xhigh`
     - PR necessity auditor, findings auditor, and live UI workers: `gpt-5.5-extra-high`
     - if the harness exposes a generic Subagent/Task API instead of named profiles, pass the matching `model` argument on every launch
   - Give each worker the scope packet.
   - Give each worker a distinct angle chosen from the actual change:
     - correctness/regressions
     - tests/validation
     - simplicity/maintainability
     - types/API contracts
     - security
     - performance
     - deletion-safety
     - state-machine behavior
   - If `runtime-harnesses.md` says the active harness cannot fan out from the current context, run them as that file directs and state why.
   - This phase is blocking as a phase: after both reviewer workers are launched, do not start live UI verification, findings audit, or controller judgment until both reviewer outputs are available.
   - Keep the parallel lanes concurrency-safe:
     - Prefer file reads, local source inspection, SCSI/base-context queries, `git show`/`git diff` reads, isolated `/tmp` reproductions, and verification commands that improve finding validity or coverage.
     - Allow non-mutating verification at whatever depth is needed, including expensive static analysis or full suites, when outputs/caches are read-only or isolated away from shared repo/runtime state. Performance cost alone is not a reason to skip useful verification.
     - Do not start dev servers, watchers, database migrations, package installs, code generators, formatters, fixture seeders, or commands that write repo-local caches/artifacts from reviewer lanes.
     - If stronger verification requires shared-state mutation, a shared service, or an exclusive runtime resource, return `verification_needed` with the exact command/setup and let the controller run it serially after aggregation or during the act phase.
   - Each candidate finding must include a reachability statement for the claimed path. If the claimed UI/API/state path may be unreachable, the worker must verify reachability before assigning severity or mark it as a hypothesis for the controller to verify/drop.

4. **Run conditional live UI verification.**
   - After both reviewers finish, run `live-ui-review`.
   - `live-ui-review` is the only worker lane that may need tool-level non-read-only mode.
   - Use non-read-only mode only to run Playwriter/browser commands and explicit local/dev runtime data setup against verified targets.
   - Mode boundary: default `live-ui-review` is verification-only.
   - Keep behavior-level read-only constraints in the prompt:
     - no repo edits
     - no file writes except Playwriter artifacts under `/tmp`
     - no GitHub mutations
     - no git writes
     - no commits or pushes
   - For post-fix UI verification, launch a separate fix-capable Playwriter task after judgment.
   - Include the live UI target/preflight block from this skill in the worker prompt.
   - Do not rely on the worker to rediscover it.
   - It returns one of:
     - `Not applicable`
     - comparison evidence
     - target/branch/data blocker for the controller to surface
   - Do not automatically rerun a blocked live-UI result.
   - A read-only/Ask-mode Playwriter block is a valid blocker to surface.

5. **Run findings audit on candidate findings.**
   - Run this phase only after the PR necessity gate, both reviewer outputs, and live UI evidence/non-applicability/target-branch-data blocker are available.
   - Always audit the reviewer findings, any worker-reported `verification_needed`, live UI evidence, and any PR necessity draft concerns that survived the greenlight gate.
   - Inline the audit in the controller when the remaining set is trivial:
     - no candidate findings, or
     - one straightforward evidence-backed finding with no model disagreement, no live UI blocker, no surviving PR-necessity concern, and no fix diff to audit.
   - Delegate to `findings-auditor` when the remaining set is non-trivial:
     - two or more candidate findings
     - any HIGH/CRITICAL candidate
     - model disagreement or likely duplication
     - any worker-reported `verification_needed` that materially affects actionability
     - any surviving PR necessity concern
     - live UI comparison/blocker evidence that materially affects judgment
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
6. **Aggregate.** Combine `pr-necessity-auditor` greenlight/skip status, GPT reviewer output, Opus reviewer output, any reviewer `verification_needed`, `live-ui-review` evidence or skip/blocker status, and the findings audit result.
7. **Judge in the controller.**
   - Apply mode-correct reconciliation:
     - all modes: collapse duplicate worker findings, apply the severity model, and keep only implementation-verified, net-new findings
     - PR modes: apply `pr_common.md` Deduplication + Truth Filter, Existing Pending Review Reconciliation, CI Coverage Gate, and PR Necessity + Correctly-Open Audit classifications
     - local-changes mode: do not apply PR-thread deduplication or PR CI coverage exemptions; judge against the staged/unstaged/range scope in the packet
   - For PR modes, read any current-account pending review and already-submitted current-account review comments/replies before drafting payloads. Merge kept pending findings with net-new findings into one final draft; drop stale pending findings with evidence; block rather than producing competing or contradictory payloads.
   - Drop:
     - unsupported claims
     - unreachable-path findings
     - PR-mode findings covered by verified PR CI or existing PR artifacts
     - findings that only a worker asserted without evidence
     - PR necessity claims that rely only on ambient precedent without proving the current PR's actual diff and directly referenced artifacts
   - For any surviving `verification_needed`, either:
     - run the serial non-mutating/heavy check in the controller before acting when it is required to keep/drop the finding, or
     - carry it forward as explicit remaining uncertainty/blocker when the check is unsafe, out of scope, or not needed for the final judgment.
8. **Act only after judgment.** Branch strictly on the mode, explicit fix intent, and `authorship` recorded in step 1; never infer self-review from the fact that the change is checked out locally.
   - Local changes or self-review with `authorship: self`:
     - apply the selected fixes in the working tree
     - run the repo's discovered quality gates
     - run the normal post-review stage over the fix diff
     - verify the actual fix diff is not redundant, verbose, semantically/logically duplicated, incomplete, or overengineered
   - PR fix/thread modes:
     - apply selected fixes only when `authorship: self` or the user explicitly asked to fix/take over that PR
     - otherwise draft replies/suggestions according to `pr_fix.md`
     - human-visible publishing stays gated
   - `authorship: other` or `unknown` without an explicit fix/takeover request:
     - draft public-ready comments/suggestions only
     - do not edit code
     - do not run fixes
     - do not post

## PR necessity audit

`pr-necessity-auditor` is part of the PR-mode flow for other-authored or unknown-author PRs. It answers whether the PR itself is sensible, correctly open, and still needed.

- It is the first blocking review worker after routing; reviewer fan-out does not start until this auditor greenlights the PR for implementation review.
- It audits author intent from the complete PR description, discussion, review threads, referenced issues/PRs, and linked artifacts.
- It checks whether the PR is correctly open: open/draft state, base/head target, scope, linked issue status, stale/conflicting context, and whether the described problem still exists.
- It searches for duplicate, overlapping, superseding, or recently merged cross-cutting work in GitHub, git history, and Slack topic discussions when Slack tools are available.
- It returns evidence and classifications only; it never decides, posts, resolves, edits, commits, or pushes.
- The controller turns supported concerns into draft feedback/questions only after normal judgment and human-visible publication gates.

## Live UI review

`live-ui-review` is part of the default flow after the blocking PR necessity gate and reviewer fan-out phases complete.

- It verifies UI/runtime-relevant findings against the configured Kibana targets.
- It returns evidence or a blocker.
- Default mode: verification only; no repo edits, posts, resolves, commits, pushes, or decisions.
- It may create minimal isolated data in the configured local/dev runtime when required to verify an applicable UI finding. It must clean up that data when safe or report leftovers exactly.
- Fix mode: separate Playwriter task after controller judgment.
- Fix mode requires `authorship: self` or explicit user takeover.
- Fix mode prompt must state allowed changes and verification commands.

Before launching `live-ui-review`, include this exact target/preflight block in the worker prompt:

```text
Runtime targets:
- Base branch: http://kibana-main.local:5602
- PR/head branch: http://kibana-feat.local:5601

Required preflight:
- Read ~/.agents/skills/playwriter/SKILL.md and run `playwriter skill` before checking targets.
- Run in a fresh Playwriter session owned by this worker.
- Store owned pages in `state.basePage` and `state.headPage`; do not reuse generic `page`.
- Close only pages this worker created, or leave their URLs in the blocker/evidence.
- Use Playwriter to check both exact targets for reachability/readiness.
- Verify branch identity with Playwriter evidence where possible.
- First perform readiness only; do not compare UI until both targets pass readiness.
- Stop after at most two navigations per target during readiness.
- Stop after at most one repeated same-URL/same-snapshot observation.
- A blocker is invalid unless it reports results for both exact target URLs.
- Do not fall back to localhost unless the user explicitly overrides the targets.
- Do not use WebFetch, shell `curl`, or other HTTP-only probes as target readiness evidence. They may be supplemental diagnostics, but Playwriter is the required readiness check.
- Do not return `Not applicable` because the target has no data. If the relevant UI exists but data is missing, inspect PR/issue media, tests, fixtures, and mocks; try browser/route mocks or existing seeded data; if still needed, create the smallest isolated local/dev Kibana/Elasticsearch data required to verify the flow.
- Mutating local/dev runtime data via Playwriter/browser actions or local API calls is allowed for verification after target readiness/identity is established. Do not mutate production/shared cloud/GitHub/git/repo files. Clean up created runtime data when safe, or report exact leftovers and cleanup uncertainty.
- If Playwriter cannot run because the harness is read-only/Ask-mode, return `Blocked`.
- If Playwriter fails before navigation with `browserType.connectOverCDP: Timeout`:
  - replace the relay once with `playwriter serve --host 127.0.0.1 --replace`
  - create a fresh session
  - smoke-test `context.pages()`
- If the smoke test fails, return `Blocked`; do not navigate or refresh target pages.
- If Playwriter loops, reloads repeatedly, or cannot reach a stable snapshot, return `Blocked`.
```

Controller validation: reject and rerun any `live-ui-review` result that:

- reports only generic localhost probing
- omits either exact target URL
- uses WebFetch or shell/HTTP probes as readiness evidence
- skips Playwriter target checks
- claims targets are unavailable without showing the exact target/preflight evidence above
- omits applicability, exact URLs checked, Playwriter preflight status, readiness result for each target, branch/runtime evidence, comparison evidence for each checked candidate, page cleanup/owned-page URLs, and blockers/uncertainty

Do not reject or rerun a result that reports a valid Playwriter harness blocker:

- read-only/Ask-mode blocked `playwriter skill` or Playwriter commands
- both exact target URLs were attempted or explicitly blocked before navigation
- repeated reload/same-URL/same-snapshot loop was detected within the budget

## Output

Return:

- `Base context:` line from the review methodology.
- Worker selection summary for each delegated phase, including any fallback reason.
- PR necessity audit summary, review greenlight, merge-readiness/status blockers or uncertainty, skip, or blocker status when applicable.
- Investigation summary: what each reviewer, live UI reviewer, and findings audit found, including whether the findings audit was inline or delegated.
- Serial verification: any `verification_needed` returned by reviewer lanes and whether the controller ran, skipped, or blocked on it.
- Controller judgment: findings kept/dropped and why.
- Pending review reconciliation: none found, reused existing, merged replacement needed, stale pending dropped, or blocked with reason.
- Action taken or draft payloads, depending on mode.
- Remaining uncertainty or gated side effects.
- `Compatibility impact: none | removed (requested) | kept existing (requested)`.
