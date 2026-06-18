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

## Findings auditor

Use after the two reviewer workers finish, before controller action.

The subject is:

- not the original review target
- not a working-tree fix
- the candidate finding set produced by the reviewer workers

Load `~/.agents/skills/review/references/judging_core.md`.

Apply only the **Post-Review Lens (The Four Dimensions)**.

Do not run:

- full coverage checklist
- base-context gate
- semantic search gate
- GitHub machinery

Scope:

- Audit the combined candidate findings from `review-gpt-5-5-extra-high` and `review-opus-4-8-xhigh-non-thinking`.
- If the parent explicitly names a commit range, staged set, uncommitted diff, or files, audit that fix diff instead.

Hard constraints:

- Strictly read-only: never edit files, never run state-changing commands, never post to GitHub, and never decide what should be fixed or commented on.
- Verify every hygiene finding from evidence; do not assert a problem without an exact anchor.
- Group findings by the canonical dimensions: redundancy, verbosity, semantic + logical duplication, gaps.

Return each finding with:

- where
- what is wrong
- why it matters
- smallest proposed cleanup

If a dimension is clean, say so for that dimension. Do not return raw diffs or logs.

## Live UI review

Use after reviewer workers as the conditional UI/runtime verifier.

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

Return: applicability, target readiness, branch evidence, comparison evidence, and any blocker.
