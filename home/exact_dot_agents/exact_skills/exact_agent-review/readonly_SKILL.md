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
- no live-UI checks
- no posting or resolving
- no commits or pushes
- no fix application

Workers only investigate and return candidate findings.

All side effects happen later in the controller, gated by step 7.

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
- launching the two reviewer workers and the findings auditor
- running conditional `live-ui-review` verification for UI/runtime-relevant changes
- aggregating worker outputs, `live-ui-review` evidence or skip/blocker status, and audit output
- judging kept/dropped findings after aggregation
- applying fixes, drafting payloads, or touching GitHub only after the relevant `review`/`github`/`git` gates

Before fan-out, the controller must not load or run the full `review` skill.

It may load only one router section first:

- Resolve `authorship` using the review router's Role Detection procedure (`~/.agents/skills/review/SKILL.md`).
- Do this before fan-out because step 7 depends on that value.
- Do not infer authorship from the change being checked out locally.
- A branch tracking another person's fork is `other`.
- Commits authored by someone else are `other`.
- If authorship cannot be verified, it is `unknown`.

After workers return, the controller may consult only the minimum relevant review references for:

- deduplication
- severity
- side-effect gates
- `~/.agents/skills/review/references/pr_common.md` for PR-mode reconciliation

Do not rerun the coverage checklist, base-context investigation, or worker review analysis.

Reviewer workers own the full investigation methodology.

- Shared runtime contract: `~/.agents/skills/agent-review/references/runtime-contracts.md`.
- Load inside each worker context:
  - `~/.agents/skills/review/SKILL.md`
  - `~/.agents/skills/review/references/judging_core.md`
  - `~/.agents/skills/review/references/shared_rules.md`
  - selected mode file under `~/.agents/skills/review/references/`
  - `~/.agents/skills/review/references/pr_common.md` for PR modes
- Return only evidence and candidate findings.
- Never edit, post, resolve, commit, push, or decide what should be fixed/commented on.

The active harness owns subagent discovery and invocation.

- Read `~/.agents/skills/agent-review/references/runtime-harnesses.md` only for capability caveats.
- Never invent a custom-agent layer the harness does not expose.

## Default orchestration

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

2. **Launch two investigation reviewers in parallel.**
   - Emit both reviewer launches in one message (a single tool-call batch).
   - Use the current harness's native configured reviewer workers or task mechanism.
   - Cursor model selection is explicit, never inherited:
     - GPT/default lane: `gpt-5.5-extra-high`
     - Opus lane: `claude-opus-4-8-xhigh`
     - findings auditor and live UI workers: `gpt-5.5-extra-high`
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

3. **Run conditional live UI verification.**
   - After both reviewers finish, run `live-ui-review`.
   - `live-ui-review` is the only worker lane that may need tool-level non-read-only mode.
   - Use non-read-only mode only to run Playwriter/browser commands.
   - Mode boundary: default `live-ui-review` is evidence-only.
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
     - target/branch blocker for the controller to surface
   - Do not automatically rerun a blocked live-UI result.
   - A read-only/Ask-mode Playwriter block is a valid blocker to surface.

4. **Run findings audit on candidate findings.**
   - Run `findings-auditor` over the reviewer findings.
   - Audit for:
     - redundancy
     - verbosity
     - semantic + logical duplication
     - gaps
   - This is still investigation, not a decision.
5. **Aggregate.** Combine GPT reviewer output, Opus reviewer output, `live-ui-review` evidence or skip/blocker status, and the findings audit.
6. **Judge in the controller.**
   - Apply mode-correct reconciliation:
     - all modes: collapse duplicate worker findings, apply the severity model, and keep only implementation-verified, net-new findings
     - PR modes: apply `pr_common.md` Deduplication + Truth Filter and CI Coverage Gate
     - local-changes mode: do not apply PR-thread deduplication or PR CI coverage exemptions; judge against the staged/unstaged/range scope in the packet
   - Drop:
     - unsupported claims
     - PR-mode findings covered by verified PR CI or existing PR artifacts
     - findings that only a worker asserted without evidence
7. **Act only after judgment.** Branch strictly on the mode, explicit fix intent, and `authorship` recorded in step 1; never infer self-review from the fact that the change is checked out locally.
   - Local changes or self-review with `authorship: self`:
     - apply the selected fixes in the working tree
     - run the repo's discovered quality gates
     - run the normal post-review stage over the fix diff
   - PR fix/thread modes:
     - apply selected fixes only when `authorship: self` or the user explicitly asked to fix/take over that PR
     - otherwise draft replies/suggestions according to `pr_fix.md`
     - human-visible publishing stays gated
   - `authorship: other` or `unknown` without an explicit fix/takeover request:
     - draft public-ready comments/suggestions only
     - do not edit code
     - do not run fixes
     - do not post

## Live UI review

`live-ui-review` is part of the default flow.

- It verifies UI/runtime-relevant findings against the configured Kibana targets.
- It returns evidence or a blocker.
- Default mode: evidence only; no edits, posts, resolves, commits, pushes, or decisions.
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

Do not reject or rerun a result that reports a valid Playwriter harness blocker:

- read-only/Ask-mode blocked `playwriter skill` or Playwriter commands
- both exact target URLs were attempted or explicitly blocked before navigation
- repeated reload/same-URL/same-snapshot loop was detected within the budget

## Output

Return:

- `Base context:` line from the review methodology.
- Investigation summary: what each reviewer and findings auditor found.
- Controller judgment: findings kept/dropped and why.
- Action taken or draft payloads, depending on mode.
- Remaining uncertainty or gated side effects.
- `Compatibility impact: none | removed (requested) | kept existing (requested)`.
