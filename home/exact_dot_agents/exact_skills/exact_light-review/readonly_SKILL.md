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
- the change is **light-eligible** by the predicate below (self-authored, no PR, none of the escalation triggers)

## Light-Eligibility Predicate (Evaluate First)

Evaluate this before reviewing; it replaces any subjective "is this low-risk?" judgment.
This section is the single source for the light-vs-`review` routing decision;
the `review` router and the delegated `change-auditor` reference it rather than re-listing triggers.

The change is **light-eligible** only when **none** of these escalation triggers holds:

- **A PR is involved:** a PR exists for the branch (`,gh-prw --number` resolves) or the user wants a thorough or GitHub-delivered result.
- **Not self-authored:** do not assume `self` just because the change is checked out locally.
  Uncommitted or staged working-tree edits are `self`; for a named commit range, verify authors with `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false log --format='%an <%ae>' <base>..HEAD` compared against `git config user.email`, and confirm the tracked remote is not another person's fork.
  Any non-self commit, another person's fork, or unverifiable authorship escalates.
- **Risk-class paths:** the diff touches security, auth/authz, crypto, secret-handling, migration, persisted-data, or public-API surfaces.
- **Deletion or replacement:** the diff deletes files/exports or replaces/migrates an implementation, test, or helper (`git diff --diff-filter=D --stat` non-empty, or removed `export`s).
- **State-machine behavior:** parser/tokenizer/formatter, routing/matching, retry/workflow, permission-matrix, or multi-flag control flow (the State-Machine Verification Gate would run with full rigor).
- **Base context beyond direct local reads:** a finding's correctness depends on base behavior that `git show <base>:<path>` + `rg` or local file reads cannot settle (mandatory SCSI base-context).

If any trigger holds, stop and escalate to `~/.agents/skills/review/SKILL.md` (its Role Detection owns the authorship procedure);
do not edit code here. If a trigger surfaces mid-pass, stop and switch to `review` rather than half-doing the heavy machinery.

## Workflow (verify and fix in place)

1. **Scope.**
   Inspect `git status --porcelain=v1 -b` and the diff (`git diff`, `git diff --staged`, or `git diff <range>` / `git log --oneline <range>`).
   If there are no diffs, say so and stop.
2. **Base context (opt-in).** Default off.
   Establish base context when a finding's correctness genuinely depends on how base behaves today;
   use the most direct sufficient source (`git show <base>:<path>` + `rg`, or local file reads).
   Do not omit needed base context because SCSI would be heavier; escalate to the full `review` skill when direct local reads are not enough.
3. **Run the Verify-and-Fix Loop** (`judging_core.md`): build the findings queue → Candidate Refutation Ladder → Findings-Set Audit → fix in the working tree → quality gates → Post-Review Stage over the fix diff.
   The **Post-Review Lens (The Four Dimensions)** and **Post-Review Stage** are foregrounded for this skill.
   Do not commit or push unless explicitly asked.

## Output

- Findings: what was found, what was fixed, what was verified (ordered by severity).
- Mechanical gates: what was run, pass/fail.
- Post-review: hygiene findings on the fix diff (by dimension) and how they were resolved.
- Remaining: anything not fixed (and why), plus any escalation recommendation.
- `Compatibility impact: none | removed (requested) | kept existing (requested)`.
