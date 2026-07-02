---
name: light-review
description: "Use when running a local/ad-hoc proportional audit of low-risk self-authored changes; escalate PRs/risky changes to review."
---

# Light Review

A proportional-depth review for a self-authored changeset you want checked and fixed in place.
It shares the same judging engine as the full `review` skill but drops PR/GitHub scaffolding when that scaffolding is not needed.
Reduced scaffolding is not reduced rigor: the SOP rules about internal time/effort estimates still apply, and any finding that needs base context, state-machine verification, or heavier evidence must trigger escalation instead of being skipped.

Load `~/.agents/skills/review/references/judging_core.md` and apply its Coverage Checklist, Severity, the relevant gates (Deletion-Safety / Historical-Rationale / State-Machine / Product-Flow / Signal-Quality / Systemic-Risk when triggered), and — foregrounded for this skill — the **Post-Review Lens (The Four Dimensions)** and **Post-Review Stage**.

Use when:

- the user asks `/light-review`, or for a local/ad-hoc review of the current changes
- the target is a self-authored changeset (uncommitted, staged, or a named commit range) that is low-risk
- the change can be judged locally without PR/GitHub scaffolding or mandatory SCSI base-context

Do not use (escalate to `~/.agents/skills/review/SKILL.md` instead) when:

- the target is a PR, or someone else's code (PR review / PR fix modes, GitHub delivery)
- base-branch context is genuinely needed to judge correctness (SCSI / `git show <base>`)
- the change is risky, security-sensitive, or stateful/parser-like enough that the State-Machine Verification Gate must run with full rigor
- the user explicitly wants the thorough review or a GitHub-delivered result

If any escalation trigger applies mid-pass, stop and switch to the `review` skill rather than half-doing the heavy machinery here.

## Workflow (verify and fix in place)

1. **Scope.**
   Inspect `git status --porcelain=v1 -b` and the diff (`git diff`, `git diff --staged`, or `git diff <range>` / `git log --oneline <range>`).
   If there are no diffs, say so and stop.
2. **Base context (opt-in).** Default off.
   Establish base context when a finding's correctness genuinely depends on how base behaves today;
   use the most direct sufficient source (`git show <base>:<path>` + `rg`, or local file reads).
   Do not omit needed base context because SCSI would be heavier; escalate to the full `review` skill when direct local reads are not enough.
3. **Judge.** Walk the diff against the Coverage Checklist (`judging_core.md`), ordered by severity.
   Verify each finding from evidence (`/tmp` repro or the smallest safe worktree experiment); drop unverified findings.
4. **Fix in the working tree.** Apply the smallest correct change for each finding now. Do not commit or push unless explicitly asked.
5. **Mechanical gates.** Run the repo's lint + type_check + tests (discover commands from the repo; do not guess).
   Fix until green or report what remains.
6. **Post-review stage (foregrounded).**
   Run the Post-Review Stage (`judging_core.md`) over the **fix diff** — the changes this pass made — applying the four dimensions:
   redundancy, verbosity, semantic + logical duplication, gaps.
   Resolve each hygiene finding in the working tree; re-run gates if those fixes touched code.

## Output

- Findings: what was found, what was fixed, what was verified (ordered by severity).
- Mechanical gates: what was run, pass/fail.
- Post-review: hygiene findings on the fix diff (by dimension) and how they were resolved.
- Remaining: anything not fixed (and why), plus any escalation recommendation.
- `Compatibility impact: none | removed (requested) | kept existing (requested)`.
