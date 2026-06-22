# Agent Review Reviewer Worker Contract

Shared contract for `/agent-review` runtime subagents. Load this file only for the matching worker role.

## Role: Reviewer worker

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
- For replacements and test migrations, classify candidates with the Replacement/Migration Parity Gate from `judging_core.md` before returning them. Return only `parity_gap`, `new_regression`, or `scope_expansion` as actionable findings. Do not return `preserved_limitation` or `prose_drift` as actionable findings.
- Verify the claimed path is reachable before assigning severity. If reachability is uncertain, say what remains unverified and return it as a hypothesis for the controller instead of an actionable finding.
- Keep probe output bounded: use path-scoped searches, exact symbols, file globs, `git show <ref>:<path>`, and targeted line ranges. Do not emit broad repo-wide search output, full logs, or full generated files when a summary plus exact anchors is sufficient.
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
