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

- Strictly read-only: never edit files, never run state-changing commands, never post or submit to GitHub.
- This contract takes precedence over mode-file instructions that would normally fix, post, or run side effects directly.
- Establish base context exactly as the review skill requires.
- Verify every finding from evidence; drop guesses and duplicates.
- Verify the claimed path is reachable before assigning severity. If reachability is uncertain, say what remains unverified and return it as a hypothesis for the controller instead of an actionable finding.
- Where a mode would normally fix or post, report the precise fix or draft comment for the parent controller to act on.

Return only findings for the assigned angle, ordered by severity.

Include:

- `Base context: ...`
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
- `similar_or_recent_work`: none found / open overlap / recently merged overlap / superseded / unknown, with links and comparison
- `greenlight`: yes / no, with the precise reason. Use `yes` only when no unresolved blocker and no supported classification makes implementation review premature or unnecessary.
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
- the live UI evidence/non-applicability/blocker status
- any PR necessity draft concerns that survived the greenlight gate

Load `~/.agents/skills/review/references/judging_core.md`.

Apply only the **Post-Review Lens (The Four Dimensions)**.

Do not run:

- full coverage checklist
- base-context gate
- semantic search gate
- GitHub machinery

Scope:

- Audit the combined candidate findings from `review-gpt-5-5-extra-high`, `review-opus-4-8-xhigh-non-thinking`, `live-ui-review`, and any surviving `pr-necessity-auditor` draft concerns when the controller determines the set is non-trivial enough to delegate.
- If the parent explicitly names a commit range, staged set, uncommitted diff, or files, audit that fix diff instead.

Hard constraints:

- Strictly read-only: never edit files, never run state-changing commands, never post to GitHub, and never decide what should be fixed or commented on.
- Verify every hygiene finding from evidence; do not assert a problem without an exact anchor.
- Group findings by the canonical dimensions: redundancy, verbosity, semantic + logical duplication, gaps.
- Check whether each remaining finding is actionable and whether the proposed smallest fix is overengineered for the proved problem.

Return each finding with:

- where
- what is wrong
- why it matters
- smallest proposed cleanup
- actionability / overengineering note when relevant

If a dimension is clean, say so for that dimension. Do not return raw diffs or logs.

## Live UI review

Use after the blocking PR necessity gate and reviewer workers as the conditional UI/runtime verifier.

Mode boundary:

- Default `live-ui-review`: evidence only.
- Tool-level non-read-only is allowed only for Playwriter/browser commands.
- Behavior-level read-only still applies in default mode.
- Fix-capable Playwriter tasks are separate post-judgment tasks.
- Fix mode requires `authorship: self` or explicit user takeover.
- Fix mode prompt must state allowed changes and verification commands.

The parent supplies:

- scope packet
- changed paths
- candidate findings
- expected base branch
- expected PR/head branch

### Applicability

Decide whether the changed paths or candidate findings touch UI/runtime behavior. If not, return `Not applicable` with the evidence used.

### Runtime targets

- Base branch: `http://kibana-main.local:5602`
- PR/head branch: `http://kibana-feat.local:5601`

### Preflight

- Follow `~/.agents/skills/playwriter/SKILL.md` and run `playwriter skill` before checking targets.
- Use a fresh Playwriter session owned by this worker.
- Store owned pages in `state.basePage` and `state.headPage`; do not use generic `page`.
- Remember that Playwriter sessions isolate `state`, but browser pages are shared.
- Do not reuse pages from other sessions or unrelated worktrees.
- Close only pages this worker created, or report their URLs in the final evidence.
- Use Playwriter to check both targets are reachable and Kibana-ready.
- Verify target branch identity with Playwriter evidence where possible.
- If readiness or branch identity cannot be established, return `Blocked` with the missing evidence.
- Do not ask for readiness during normal flow; the controller surfaces only blockers.
- Do not use WebFetch, shell `curl`, or other HTTP-only probes as local/private Kibana readiness evidence.
- HTTP-only probes may be supplemental diagnostics only.
- Playwriter is the required readiness check for:
  - `kibana-main.local`
  - `kibana-feat.local`
  - localhost aliases
- A `Blocked` result is invalid unless it reports results for both exact target URLs above, or an explicit user-provided target override.

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
- Use non-mutating probes only: browser inspection, HTTP requests, screenshots/paths when available, logs, or read-only CLI commands.
- Capture concrete evidence: URLs, steps, screenshots/paths when available, observed differences, and uncertainty.
- Bound comparison to the smallest flow that can verify a candidate finding.
- Stop after five UI actions for a single candidate unless the parent supplied a tighter budget.
- Return partial evidence plus `Blocked` if the flow needs more actions or data setup.

Hard constraints for this evidence pass:

- Investigation only. Never edit files, post comments, resolve threads, commit, push, or decide what the controller should fix/comment on.
- Never run git write commands.
- Never use ApplyPatch or file-editing tools.
- Never write files except Playwriter artifacts under `/tmp`.
- If the harness is read-only/Ask-mode and blocks Playwriter, return `Blocked`.
- If Playwriter loops, reloads repeatedly, or cannot reach a stable snapshot, return `Blocked`.
- Return findings to the user or `/agent-review` as evidence input. `/agent-review` performs any judgment or side effects.

Return exactly:

- `applicability`: applicable / not applicable, with changed-path or finding evidence
- `urls_checked`: the exact base and PR/head URLs, or an explicit blocker before navigation
- `playwriter_preflight`: whether the Playwriter skill was loaded and `playwriter skill` was run; if not, say why
- `target_readiness`: readiness result for each exact URL, from Playwriter evidence
- `branch_evidence`: branch/runtime identity evidence for each target, or what could not be verified
- `comparison_evidence`: candidate-by-candidate UI/runtime evidence, including `Not applicable` for candidates disproved by reachability
- `pages`: pages created and closed, or URLs left open
- `blockers_or_uncertainty`: none, or precise blockers/remaining uncertainty
