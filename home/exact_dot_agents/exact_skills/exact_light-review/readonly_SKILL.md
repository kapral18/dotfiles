---
name: light-review
description: Light, in-place audit of a changeset (working tree, staged set, or commit range) without the full review machinery — no mandatory SCSI/base-context, no GitHub. Use for low-risk, self-authored changes where you want a fast verify-and-fix pass with the four-dimension hygiene lens foregrounded. Escalate to the review skill for PRs, others' code, risky/stateful changes, or when base-branch context is needed.
---

# Light Review

A proportional-depth review for a self-authored changeset you want checked quickly and fixed in place. It shares the same judging engine as the full `review` skill but drops the mandatory PR/SCSI/GitHub scaffolding. Depth is the only axis that differs — the judging core is identical.

Load `~/.agents/skills/review/references/judging_core.md` and apply its Coverage Checklist, Severity, the relevant gates (Deletion-Safety / Historical-Rationale / State-Machine when triggered), and — foregrounded for this skill — the **Post-Review Lens (The Four Dimensions)** and **Post-Review Stage**.

Use when:

- the user asks `/light-review`, or for a quick/light/ad-hoc review of the current changes
- the target is a self-authored changeset (uncommitted, staged, or a named commit range) that is low-risk
- you want a fast verify-and-fix pass without spinning up SCSI base-context or GitHub

Do not use (escalate to `~/.agents/skills/review/SKILL.md` instead) when:

- the target is a PR, or someone else's code (PR review / PR fix modes, GitHub delivery)
- base-branch context is genuinely needed to judge correctness (SCSI / `git show <base>`)
- the change is risky, security-sensitive, or stateful/parser-like enough that the State-Machine Verification Gate must run with full rigor
- the user explicitly wants the thorough review or a GitHub-delivered result

If any escalation trigger applies mid-pass, stop and switch to the `review` skill rather than half-doing the heavy machinery here.

## Workflow (verify and fix in place)

1. **Scope.** Inspect `git status --porcelain=v1 -b` and the diff (`git diff`, `git diff --staged`, or `git diff <range>` / `git log --oneline <range>`). If there are no diffs, say so and stop.
2. **Base context (opt-in).** Default off. Establish base context only if a finding's correctness genuinely depends on how base behaves today; then use the cheapest source (`git show <base>:<path>` + `rg`, or local file reads). Do not run the mandatory SCSI preflight — that belongs to the full `review` skill.
3. **Judge.** Walk the diff against the Coverage Checklist (`judging_core.md`), ordered by severity. Verify each finding from evidence (`/tmp` repro or the smallest safe worktree experiment); drop unverified findings.
4. **Fix in the working tree.** Apply the smallest correct change for each finding now. Do not commit or push unless explicitly asked.
5. **Mechanical gates.** Run the repo's lint + type_check + tests (discover commands from the repo; do not guess). Fix until green or report what remains.
6. **Post-review stage (foregrounded).** Run the Post-Review Stage (`judging_core.md`) over the **fix diff** — the changes this pass made — applying the four dimensions: redundancy, verbosity, semantic + logical duplication, gaps. Resolve each hygiene finding in the working tree; re-run gates if those fixes touched code.

## Output

- Findings: what was found, what was fixed, what was verified (ordered by severity).
- Mechanical gates: what was run, pass/fail.
- Post-review: hygiene findings on the fix diff (by dimension) and how they were resolved.
- Remaining: anything not fixed (and why), plus any escalation recommendation.
- `Compatibility impact: none | removed (requested) | kept existing (requested)`.
