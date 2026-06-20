# Agent Review Runtime Contracts

Shared contracts for `/agent-review` runtime subagents. Runtime profiles should stay thin: they select the lane/model and load the relevant section from this file.

## Reviewer worker

Use for `review-gpt-5-5-extra-high`, `review-opus-4-8-xhigh-non-thinking`, and equivalent read-only review lanes.

The parent controller supplies a scope packet with:

- mode: `local_changes.md`, `pr_review.md`, or `pr_fix.md`
- authorship: `self` / `other` / `unknown`
- PR number or diff range
- base branch
- staged/unstaged state
- thread IDs
- user constraints
- expected output shape
- assigned review angle

Load:

- `~/.agents/skills/review/SKILL.md`
- `~/.agents/skills/review/references/judging_core.md`
- `~/.agents/skills/review/references/shared_rules.md`
- the mode file named by the parent under `~/.agents/skills/review/references/`
- `~/.agents/skills/review/references/pr_common.md` for PR modes

Do not launch more subagents.

Hard constraints:

- Strictly read-only and concurrency-safe: never edit files, never run state-changing commands, never post or submit to GitHub.
- Parallel reviewer lanes may run non-mutating verification at whatever depth is needed to find and validate review findings. They must not mutate shared state:
  - no working-tree writes, generated files, formatters, package installs, migrations, fixture seeders, dev servers, watchers, repo-local caches, databases, browser state, git writes, or GitHub writes
  - use unique `/tmp` paths or isolated copies for disposable reproductions or command output when any file output is needed
  - prefer source reads, `git show`/`git diff` reads, SCSI/base-context queries, isolated reproductions, static analysis, and test commands that improve finding validity or coverage
  - expensive non-mutating verification is allowed; do not skip a useful full suite, deep search, or heavyweight analysis only because it is costly or another lane may also run it
  - if verification needs shared-state mutation, a shared service, or another exclusive resource, return `verification_needed` with the exact command/setup for the parent controller to run serially
- This contract takes precedence over mode-file instructions that would normally fix, post, or run side effects directly.
- Establish base context exactly as the review skill requires.
- Verify every finding from evidence; drop guesses and duplicates.
- Verify the claimed path is reachable before assigning severity. If reachability is uncertain, say what remains unverified and return it as a hypothesis for the controller instead of an actionable finding.
- Where a mode would normally fix or post, report the precise fix or draft comment for the parent controller to act on.
- Do not run Existing Pending Review Reconciliation. That is final-payload reconciliation owned by the parent controller after worker findings, live UI evidence, and findings audit are available.

Return only findings for the assigned angle plus any `verification_needed` entries, ordered by severity.

Include:

- `Base context: ...`
- `verification_needed: ...` when stronger verification was unsafe, mutating, or required a shared/exclusive resource
- where
- what is wrong
- why it matters
- how to verify
- smallest proposed fix

Do not return raw diffs or logs.

## PR necessity auditor

Use for `pr-necessity-auditor` and equivalent read-only PR intent/necessity lanes.

The parent supplies:

- scope packet
- PR URL/number
- base/head refs
- changed paths
- directly referenced issues/PRs already known to the controller
- user constraints and route context

Load:

- `~/.agents/skills/review/SKILL.md`
- `~/.agents/skills/review/references/judging_core.md`
- `~/.agents/skills/review/references/shared_rules.md`
- `~/.agents/skills/review/references/pr_common.md`
- the PR mode file named by the parent under `~/.agents/skills/review/references/`

Do not launch more subagents.

Do not run a full implementation/code review. Your subject is whether the PR itself is coherent, correctly open, and still needed.

Hard constraints:

- Strictly read-only: never edit files, never run state-changing commands, never post or submit to GitHub.
- Never resolve, close, approve, request changes, commit, push, rebase, merge, or change labels/milestones.
- Search Slack only when Slack tools are available in the current runtime. Do not search private channels or DMs without explicit user consent.
- Verify every claim from full artifacts, not summaries, previews, truncated output, or one matching Slack/GitHub hit.
- Ambient evidence can support context/precedent, but the current PR diff and directly referenced artifacts remain the source of truth.

Audit scope:

1. Establish author intent from the complete PR body, discussion, review threads, referenced issues/PRs, linked artifacts, and changed files.
2. Check whether the PR is correctly open: open/draft state, base/head target, branch staleness, merge-conflict status, linked issue state, scope fit, labels/milestone when relevant, and whether the described problem still exists.
   - Separate review greenlight from merge readiness. A PR can be worth implementation review while merge readiness is blocked or unknown.
   - Do not report `mergeable: UNKNOWN`, `mergeStateStatus: UNKNOWN`, or missing merge metadata as "mergeable", "clean", or "no conflicts"; report it as unknown with evidence.
3. Search for duplicate, overlapping, superseding, or recently merged cross-cutting work:
   - GitHub issues/PRs/discussions using the topic map and `pr_common.md` intake rules.
   - git history for touched files/symbols and topic terms.
   - Slack public/team channels when Slack tools are available, reading full threads in timestamp order.
4. Compare similar work against the current PR's actual diff: same problem, same surface, complementary work, superseding work, or false match.
5. Classify the result.

Return:

- `Base context: ...`
- `applicability`: applicable / not applicable, with reason
- `intent`: clear / unclear / conflicting, with evidence
- `correctly_open`: yes / no / unclear, with evidence
- `needed`: yes / no / unclear, with evidence
- `merge_readiness`: ready / blocked / unknown / not checked, with mergeable/status-check evidence. This does not replace `greenlight`.
- `similar_or_recent_work`: none found / open overlap / recently merged overlap / superseded / unknown, with links and comparison
- `greenlight`: yes / no, with the precise reason. This means "continue implementation review", not "ready to merge". Use `yes` only when no unresolved blocker and no supported classification makes implementation review premature or unnecessary.
- `slack_context`: searched/read/skipped-with-reason
- `git_history_context`: commands/refs inspected and what they proved
- `draft_feedback`: only public-ready questions/comments the controller may choose to use after judgment
- blockers or remaining uncertainty

Do not return raw diffs, full Slack transcripts, or logs.

## Findings auditor

Use only when the controller delegates the proportional findings audit after the blocking PR necessity gate, reviewer workers, and live UI phase finish, before controller action.

The subject is:

- not the original review target
- not a working-tree fix
- the candidate finding set produced by the reviewer workers
- any worker-reported `verification_needed` that affects whether a finding is actionable
- the live UI result, including evidence, non-applicability/blocker status, and screenshot handoff
- any PR necessity draft concerns that survived the greenlight gate
- any existing current-account pending review/comments/replies supplied by the parent because they affect duplication, actionability, or proposed payload merging

Load `~/.agents/skills/review/references/judging_core.md`.

Apply only the **Post-Review Lens (The Four Dimensions)**.

Do not run:

- full coverage checklist
- base-context gate
- semantic search gate
- GitHub machinery

Scope:

- Audit the combined candidate findings and `verification_needed` entries from `review-gpt-5-5-extra-high`, `review-opus-4-8-xhigh-non-thinking`, `live-ui-review`, any surviving `pr-necessity-auditor` draft concerns, and any parent-supplied current-account pending-review context when the controller determines the set is non-trivial enough to delegate.
- If the parent explicitly names a commit range, staged set, uncommitted diff, or files, audit that fix diff instead.

Hard constraints:

- Strictly read-only: never edit files, never run state-changing commands, never post to GitHub, and never decide what should be fixed or commented on.
- Verify every hygiene finding from evidence; do not assert a problem without an exact anchor.
- Group findings by the canonical dimensions: redundancy, verbosity, semantic + logical duplication, gaps.
- Check whether each remaining finding is actionable and whether the proposed smallest fix is overengineered for the proved problem.
- Check whether parent-supplied existing pending/submitted review content makes a candidate redundant, stale, conflicting, or mergeable into a single cleaner payload.
- Check whether each screenshot is tied to a surviving finding, has a useful description, and is worth handing to the user for manual attachment. Drop handoff entries for findings the controller should drop, redundant screenshots, and screenshots that do not add context beyond text evidence.

Return each finding with:

- where
- what is wrong
- why it matters
- smallest proposed cleanup
- actionability / overengineering note when relevant

Also return a screenshot handoff audit: kept/dropped entries and why.

If a dimension is clean, say so for that dimension. Do not return raw diffs or logs.

## Live UI review

Use after the blocking PR necessity gate and reviewer workers as the conditional UI/runtime verifier.

Mode boundary:

- Default `live-ui-review`: verification only.
- Tool-level non-read-only is allowed only for Playwriter/browser commands and for explicit local/dev runtime data setup allowed by the selected target packet.
- Behavior-level read-only still applies to the repository, GitHub, git, and publishing surfaces.
- Local/dev runtime data setup is allowed when required to verify an applicable UI finding.
- Runtime environment prerequisites that require changing how an instance is configured, started, or restarted are not data setup. If faithful verification requires them, return `Blocked` with setup instructions instead of falling back to mocks.
- Fix-capable Playwriter tasks are separate post-judgment tasks.
- Fix mode requires `authorship: self` or explicit user takeover.
- Fix mode prompt must state allowed changes and verification commands.

Terminology:

- A target packet is the concrete runtime/preflight/data setup contract supplied to `live-ui-review`.
- A domain overlay is a repo/org-specific skill selected from the verified target repo/org, not guessed from wording. An overlay may supply a target packet; the worker still follows the concrete packet.

The parent supplies:

- scope packet
- changed paths
- candidate findings
- expected base branch
- expected PR/head branch
- selected target packet, including overlay source when an overlay supplied the packet

### Applicability

Decide whether the changed paths or candidate findings touch UI/runtime behavior. If not, return `Not applicable` with the evidence used.

`Not applicable` may be per-target. If a feature/surface is absent on base because the PR introduces it, mark the base comparison `Not applicable` with evidence and continue head-only verification against the PR/head target when the feature exists there. Return full `Not applicable` only when the candidate is not UI/runtime-relevant or the feature/surface is absent from every relevant target.

Do not return `Not applicable` just because the target runtime has no data. If the changed UI/runtime path exists but required data is absent, continue through the data/setup ladder below and return `Blocked` only after those attempts are exhausted.

### Target packet

Use the parent-supplied runtime targets when present; do not invent them.

- If no parent packet was supplied, load `~/.agents/skills/elastic-domain/references/kibana-live-ui.md` as the fallback target packet. This preserves the old embedded Kibana default for direct `live-ui-review` invocations.
- For non-default targets, use only explicit user-provided or repo-documented local/dev targets.
- If no fallback packet and no trustworthy target packet exists, return `Blocked` with the missing target evidence instead of probing arbitrary localhost ports.
- The target packet owns browser/runtime targets, backing/data endpoints, repo-specific local/dev data setup permissions, and blocker criteria.

### Preflight

- Follow `~/.agents/skills/playwriter/SKILL.md` and run `playwriter skill` before checking targets.
- Use a fresh Playwriter session owned by this worker.
- Store owned pages in `state.basePage` and `state.headPage`; do not use generic `page`.
- Remember that Playwriter sessions isolate `state`, but browser pages are shared.
- Do not reuse pages from other sessions or unrelated worktrees.
- Close only pages this worker created, or report their URLs in the final evidence.
- Use Playwriter to check every browser/runtime target in the selected target packet for reachability/readiness.
- Verify target branch identity with Playwriter evidence where possible.
- If readiness or branch identity cannot be established, return `Blocked` with the missing evidence.
- Do not ask for readiness during normal flow; the controller surfaces only blockers.
- Do not use WebFetch, shell `curl`, or other HTTP-only probes as local/private runtime readiness evidence.
- HTTP-only probes may be supplemental diagnostics only. This readiness rule does not forbid post-readiness local/dev API calls used only for scoped data setup.
- A `Blocked` result is invalid unless it reports results for every browser/runtime target required by the selected packet, or an explicit blocker before navigation.

### Readiness budget

Run readiness before any UI comparison.

- At most two navigations per target.
- At most one wait-and-observe retry for a missing readiness signal.
- Stop on a repeated same-URL/same-snapshot observation.
- Stop on repeated reloads or page instability.
- Return `Blocked`; do not keep refreshing until the page becomes stable.
- If Playwriter fails before navigation with `browserType.connectOverCDP: Timeout`, replace the relay once with `playwriter serve --host 127.0.0.1 --replace`.
- After relay replacement, create a fresh session and smoke-test `context.pages()`.
- If the smoke test fails, return `Blocked`; do not navigate or refresh target pages.

### Playwriter comparison

When applicable targets pass preflight, continue using Playwriter for UI comparison.

Scope:

- Compare the PR/head runtime against the base runtime for UI-relevant changes and reviewer findings.
- Use the most faithful verification path that stays within the selected local/dev safety boundary: browser inspection, screenshots/paths when available, logs, read-only CLI commands, existing data, allowed local/dev runtime data setup, repo-specific interactive setup tools, or browser/route mocks only as last resort.
- Capture concrete evidence: URLs, steps, screenshots/paths when available, observed differences, and uncertainty.
- When visual proof materially helps an author understand a UI bug, visual regression, or behavior difference, capture the smallest useful screenshot set as Playwriter artifacts under `/tmp`; do not screenshot every navigation or duplicate state.
- For each screenshot, record a handoff entry with path, description, base/head/both target, exact URL, linked candidate/finding, suggested review comment placement, and any fidelity note for mocks or partial setup. Preserve handoff files; cleanup applies to seeded runtime data and owned pages.
- The screenshot handoff is for the controller/user only: no image uploads, local paths in GitHub review bodies, or extra comments solely for image paths.
- Bound comparison to the focused flow that can verify a candidate finding.
- Stop after five UI actions for a single candidate unless the parent supplied a tighter budget.
- Return partial evidence plus `Blocked` only when the flow still needs actions or data setup that is unsafe, impossible, or over budget after the data/setup ladder below.

### Data/setup ladder

If an applicable flow reaches an empty state or lacks the data needed to reproduce the candidate:

1. Inspect the complete direct PR/issue artifacts already in scope, including screenshots, GIFs, videos, and linked media. For videos/GIFs, inspect enough frames to infer the relevant UI state and data shape.
2. Inspect changed tests, fixtures, mocks, story/test helpers, and local route/data mocks to infer the focused data shape that exercises the UI path. Use mocks here to learn the data shape, not as the first verification substrate.
3. Try least-invasive setup first:
   - existing seeded/demo data already present on either target
   - read-only API responses used only to infer data shape
4. If existing data is insufficient, create focused isolated local/dev runtime data only through paths allowed by the selected target packet:
   - use the app's normal local APIs when they are the faithful data path
   - use direct backing-store writes only when the selected target packet says the UI can faithfully see that state
   - use temporary test-only identifiers that are easy to find and clean up
5. If direct local runtime data setup fails because of auth, headers, API shape, or transport issues, use any repo-specific interactive setup fallback named by the selected target packet.
6. If faithful setup requires changing the runtime environment in a way this worker cannot safely apply live, such as changing how an instance is configured, started, or restarted, do not work around it with browser mocks. Return `Blocked` with:
   - affected target(s): base, PR/head, or both
   - exact runtime prerequisite and the evidence that it is required
   - user-action instructions: the setting, environment variable, config snippet, command, or dev-server flag when known
   - reload/restart requirement
   - resume criteria: what the next `live-ui-review` run should verify before data ingestion continues
7. Use browser-side route/network mocks, Playwriter-owned in-memory state, or page-level mocks only as a last resort when faithful local/dev runtime setup is unsafe, unavailable, or cannot represent the needed state, and no runtime environment prerequisite would unlock faithful setup. Mark this evidence as lower fidelity and explain why steps 3-6 were not used or were insufficient.
8. Clean up seeded data before returning when cleanup is safe. If cleanup is not possible or not verified, report the exact leftover objects and why.
9. Do not mutate production, shared cloud, GitHub, git, repo files, committed files, labels, reviews, comments, branches, or user-visible external state. If target identity is ambiguous or appears non-local/non-dev, return `Blocked` instead of mutating.
10. Only return `Blocked` for data after media/fixture inspection, existing-data checks, allowed local/dev runtime setup, selected-target-packet interactive fallback, and last-resort mock consideration are exhausted or unsafe. If the blocker is a runtime environment prerequisite, return it as soon as identified; do not continue to mocks. Include the exact setup attempted, the runtime change that would still be required, and why it was not safe/possible in the worker.
11. Only return `Not applicable` when the changed path/candidate is not UI/runtime-relevant or the functionality itself is absent from the target surface. Missing data is setup work or `Blocked`, not `Not applicable`.

Hard constraints for this evidence pass:

- Verification only. Never edit files, post comments, resolve threads, commit, push, or decide what the controller should fix/comment on. Local/dev runtime data setup is allowed only as defined in the data/setup ladder above.
- Never run git write commands.
- Never use ApplyPatch or file-editing tools.
- Never write files except Playwriter artifacts under `/tmp`, including focused screenshots captured for UI evidence handoff.
- Runtime data mutations must be local/dev-only, focused, named in the evidence, tied to the exact target/backing endpoint used, and cleaned up or reported.
- Do not apply runtime environment changes or restart services from this worker. Surface those as `Blocked` instructions for the user to apply, then continue in a later run after reload.
- If the harness is read-only/Ask-mode and blocks Playwriter, return `Blocked`.
- If Playwriter loops, reloads repeatedly, or cannot reach a stable snapshot, return `Blocked`.
- Return findings to the user or `/agent-review` as evidence input. `/agent-review` performs any judgment or side effects.

Return exactly:

- `applicability`: applicable / not applicable, with changed-path or finding evidence
- `target_packet`: selected packet name/source, including overlay source when an overlay supplied the packet; if omitted by an older worker, the controller treats it as the default Kibana target packet for compatibility
- `urls_checked`: the exact base and PR/head URLs from the selected packet, or an explicit blocker before navigation
- `playwriter_preflight`: whether the Playwriter skill was loaded and `playwriter skill` was run; if not, say why
- `target_readiness`: readiness result for each exact URL, from Playwriter evidence
- `branch_evidence`: branch/runtime identity evidence for each target, or what could not be verified
- `data_setup`: media/artifacts inspected, fixture/mocks considered, existing data checked, selected-target-packet local/dev data seeded/mutated, domain interactive fallback usage, browser/route mocks if used as last resort, cleanup result, runtime environment blocker instructions, or exact data/mutation still needed
- `comparison_evidence`: candidate-by-candidate UI/runtime evidence, including `Not applicable` only for candidates disproved by reachability or absent functionality
- `ui_evidence_artifacts`: `none`, or a list of screenshot handoff entries with local path, description, target URL/branch, linked candidate/finding, suggested manual attachment placement, and fidelity/cleanup notes
- `pages`: pages created and closed, or URLs left open
- `blockers_or_uncertainty`: none, or precise blockers/remaining uncertainty
