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
- running conditional `live-ui-review` verification after reviewer workers finish when changed paths or kept candidate findings touch UI/runtime behavior and runtime evidence is applicable
- running the findings audit phase after live UI returns evidence/non-applicability/blocker or is explicitly skipped; delegate to `findings-auditor` only when a step 5 delegation condition is true
- aggregating worker outputs, `pr-necessity-auditor` status, reviewer findings, live UI status/evidence/artifacts/skip reason, and audit output
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
- Replacement/Migration Parity Gate classification from `judging_core.md`
- side-effect gates
- `~/.agents/skills/review/references/pr_common.md` for PR-mode reconciliation
- `~/.agents/skills/review/references/shared_rules.md` for existing pending-review awareness

Do not rerun the coverage checklist, base-context investigation, or worker review analysis.

Reviewer workers own the full investigation methodology.

- Role-specific runtime contracts live under `~/.agents/skills/agent-review/references/`.
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
4. live UI verification when changed paths or a kept candidate touch UI/runtime behavior
5. findings audit, inline or delegated by the step 5 delegation conditions
6. controller aggregation, judgment, PR-mode pending-review reconciliation, and action

Do not start a later phase until the current phase returns. In blocking phases, do not poll background workers with long waits just to check status; wait for completion notifications or use the harness's synchronous/blocking mechanism. The same rule applies after `write_agent` follow-ups for addenda or reconciliation checks: send the follow-up, state that the phase is waiting, and end the turn unless the worker has already completed. The controller may read completed phase outputs, but it must not perform later-phase analysis while the current phase is still running.

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
   - It must follow `~/.agents/skills/agent-review/references/pr-necessity-auditor.md`.
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
   - After both reviewers finish, first apply a read-only controller parity filter to replacement/test-migration candidates:
     - apply the Replacement/Migration Parity Gate from `judging_core.md` to replacement/test-migration candidates
     - drop candidates classified as `preserved_limitation` or `prose_drift`
     - do not treat test-only UI code as live-UI applicability by itself
   - Run `live-ui-review` when changed paths or any kept candidate touch UI/runtime behavior and runtime evidence is applicable. For replacement/test-migration candidates, only `parity_gap`, `new_regression`, and `scope_expansion` can be kept candidates for this trigger.
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
   - A domain overlay is a repo/org-specific skill selected from the verified target repo/org, not guessed from wording. For live UI, an overlay may provide a concrete target packet; the worker receives the packet, not an unresolved overlay concept.
   - Select a live UI target packet before launch:
     - If the target repo/object is verified as `elastic/kibana` and no explicit user-provided or repo-documented local/dev target packet exists, load `~/.agents/skills/elastic-domain/SKILL.md` and include the Kibana live-UI target packet from `~/.agents/skills/elastic-domain/references/kibana-live-ui.md`.
     - Otherwise use the explicit user-provided or repo-documented local/dev target packet.
   - Include the selected target/preflight packet in the worker prompt.
   - Do not rely on the worker to rediscover it.
   - It returns one of:
     - `Not applicable`
     - comparison evidence with `ui_evidence_artifacts` when screenshots were captured
     - target/branch/runtime/data blocker for the controller to surface
   - Do not automatically rerun a blocked live-UI result.
   - A read-only/Ask-mode Playwriter block is a valid blocker to surface.

5. **Run findings audit on candidate findings.**
   - Run this phase only after the PR necessity gate, both reviewer outputs, and the live UI result or explicit live-UI skip reason are available.
   - Always audit kept reviewer findings, worker-reported `verification_needed`, live UI evidence/artifacts/blockers or skip reason, and any PR necessity draft concerns kept after the greenlight gate.
   - Inline the audit in the controller when the remaining set is trivial:
     - no candidate findings, or
     - one straightforward evidence-backed finding with no model disagreement, no live UI blocker, no PR-necessity concern kept after greenlight, and no fix diff to audit.
   - Delegate to `findings-auditor` when the remaining set is non-trivial:
     - two or more candidate findings
     - any HIGH/CRITICAL candidate
     - model disagreement or likely duplication
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
6. **Aggregate.** Combine `pr-necessity-auditor` greenlight/skip status, GPT reviewer output, Opus reviewer output, reviewer `verification_needed`, live UI evidence/status/artifacts, and the findings audit result.
7. **Judge in the controller.**
   - Apply mode-correct reconciliation:
     - all modes: collapse duplicate worker findings, apply the severity model, and keep only findings that are implementation-verified, not covered by existing evidence, and not dropped by the parity/deduplication filters
     - PR modes: apply `pr_common.md` Deduplication + Truth Filter, Existing Pending Review Reconciliation, CI Coverage Gate, and PR Necessity + Correctly-Open Audit classifications
     - local-changes mode: do not apply PR-thread deduplication or PR CI coverage exemptions; judge against the staged/unstaged/range scope in the packet
   - For PR modes, read any current-account pending review and already-submitted current-account review comments/replies before drafting payloads. Merge kept pending findings with kept new findings into one final draft; drop stale pending findings with evidence; block rather than producing competing or contradictory payloads.
   - For kept PR-mode UI findings, verify screenshot paths when possible and surface them only in final `UI evidence attachments:`. Never upload images, put local paths in GitHub review bodies, or create extra comments just to carry image paths.
   - Drop:
     - unsupported claims
     - unreachable-path findings
     - PR-mode findings covered by verified PR CI or existing PR artifacts
     - candidates classified as `preserved_limitation` or `prose_drift` by the Replacement/Migration Parity Gate
     - findings that only a worker asserted without evidence
     - PR necessity claims that rely only on ambient precedent without proving the current PR's actual diff and directly referenced artifacts
   - For any kept `verification_needed`, either:
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

`live-ui-review` is part of the default flow after the blocking PR necessity gate and reviewer fan-out phases complete when changed paths or kept candidate findings touch UI/runtime behavior and runtime evidence is applicable. Replacement/test-migration candidates first pass through the Replacement/Migration Parity Gate; `preserved_limitation` and `prose_drift` candidates are dropped before live-UI applicability is decided.

- It verifies UI/runtime-relevant findings against a selected target packet.
- It returns evidence, optional screenshot handoff, or a blocker.
- Default mode: verification only; no repo edits, posts, resolves, commits, pushes, or decisions.
- It may create focused isolated data in the configured local/dev runtime when required to verify an applicable UI finding. It must clean up that data when safe or report leftovers exactly.
- Capture focused screenshots as Playwriter artifacts under `/tmp` only when visual proof is needed to understand a kept finding or blocker. Return paths, descriptions, target URL/branch, and suggested comment placement for manual user attachment.
- Fix mode: separate Playwriter task after controller judgment.
- Fix mode requires `authorship: self` or explicit user takeover.
- Fix mode prompt must state allowed changes and verification commands.

Before launching `live-ui-review`, include a target/preflight packet in the worker prompt.

- Verified Kibana target: if the target repo/object is `elastic/kibana` and no explicit user-provided or repo-documented local/dev target packet exists, load `~/.agents/skills/elastic-domain/SKILL.md` and paste the Kibana target/preflight packet from `~/.agents/skills/elastic-domain/references/kibana-live-ui.md`.
- Other targets: use only explicit user-provided or repo-documented local/dev targets. If neither a verified Kibana packet nor an explicit packet can be loaded, return a target blocker instead of inventing hosts or ports.
- The packet must identify base/head targets, readiness checks, allowed local/dev data setup, screenshot handoff rules, and blocker criteria.

Controller validation: reject and rerun any `live-ui-review` result that:

- does not match the selected target packet
- reports only generic localhost probing when the packet requires named targets
- omits a required base/head target from the selected packet
- uses WebFetch or shell/HTTP probes as readiness evidence
- skips Playwriter target checks
- claims targets are unavailable without showing the selected target/preflight evidence
- uses browser/route/network mocks for a data-dependent UI finding without first attempting or explicitly ruling out faithful local/dev data setup from the selected target packet
- uses browser/route/network mocks when faithful verification is blocked by a required runtime environment change; that must be returned as `Blocked` with setup instructions instead
- lists screenshot artifacts without local paths, descriptions, target URL/branch, or linked candidate/finding placement
- omits applicability, exact URLs checked, Playwriter preflight status, readiness result for each target, branch/runtime evidence, comparison evidence for each checked candidate, UI evidence artifact manifest or `none`, page cleanup/owned-page URLs, and blockers/uncertainty
- omits the selected `target_packet` source, including overlay source when an overlay supplied the packet

Do not reject or rerun a result that reports a valid Playwriter harness blocker:

- read-only/Ask-mode blocked `playwriter skill` or Playwriter commands
- both exact browser/runtime target URLs were attempted or explicitly blocked before navigation
- repeated reload/same-URL/same-snapshot loop was detected within the budget

## Output

Return:

- `Base context:` line from the review methodology.
- Worker selection summary for each delegated phase, including any fallback reason.
- PR necessity audit summary: report greenlight, merge-readiness/status blockers or uncertainty, skipped-with-reason, or blocker status.
- Investigation summary: what each reviewer, live UI reviewer, and findings audit found, including whether the findings audit was inline or delegated.
- Serial verification: any `verification_needed` returned by reviewer lanes and whether the controller ran, skipped, or blocked on it.
- Controller judgment: findings kept/dropped and why.
- Pending review reconciliation: none found, reused existing, merged replacement needed, stale pending dropped, or blocked with reason.
- Action taken or draft payloads, depending on mode.
- UI evidence attachments: for kept UI findings, local screenshot artifact paths with descriptions, target URL/branch, and suggested manual attachment placement; or `none`. Keep this separate from GitHub review bodies because local paths are only for the user.
- Remaining uncertainty or gated side effects.
- `Compatibility impact: none | removed (requested) | kept existing (requested)`.
