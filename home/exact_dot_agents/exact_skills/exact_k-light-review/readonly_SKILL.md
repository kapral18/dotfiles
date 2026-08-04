---
name: k-light-review
description: "Use for local/ad-hoc audits of low-risk self-authored changes; escalate PRs/risky changes to k-review."
---

# Light Review

A light-rigor review for a low-risk self-authored changeset you want checked and fixed in place.
It uses the same review machinery as `k-review`, but trims PR/GitHub scaffolding, live-UI work, broad base-context gathering, and multi-lane diversity when those are not needed.
Light does not mean inline-only: use one read-only `change-auditor` worker plus adversarial refutation when the active harness can launch them.

Load `~/.agents/skills/k-review/references/judging_core.md` and apply its Coverage Checklist, Severity, the relevant gates (Deletion-Safety / Historical-Rationale / State-Machine / Product-Flow / Signal-Quality / Systemic-Risk when triggered), and — foregrounded for this skill — the **Post-Review Lens (The Four Dimensions)** and **Post-Review Stage**.

Use when:

- the user asks `/k-light-review`, or for a local/ad-hoc review of the current changes
- the change is **light-eligible** by the predicate below (self-authored, no PR, none of the escalation triggers)

## Light-Eligibility Predicate (Evaluate First)

Evaluate this before reviewing; it replaces any subjective "is this low-risk?" judgment.
This section is the single source for the light-vs-`k-review` routing decision;
the `k-review` router and the delegated `change-auditor` reference it rather than re-listing triggers.

The change is **light-eligible** only when **none** of these escalation triggers holds:

- **A PR is involved:** a PR exists for the branch (`,gh-prw --number` resolves) or the user wants a thorough or GitHub-delivered result.
- **Not self-authored:** do not assume `self` just because the change is checked out locally.
  Uncommitted or staged working-tree edits are `self`; for a named commit range, verify authors with `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false log --format='%an <%ae>' <base>..HEAD` compared against `git config user.email`, and confirm the tracked remote is not another person's fork.
  Any non-self commit, another person's fork, or unverifiable authorship escalates.
- **Risk-class paths:** the diff touches security, auth/authz, crypto, secret-handling, migration, persisted-data, or public-API surfaces.
- **Deletion or replacement:** the diff deletes files/exports or replaces/migrates an implementation, test, or helper (`git diff --diff-filter=D --stat` non-empty, or removed `export`s).
- **State-machine behavior:** parser/tokenizer/formatter, routing/matching, retry/workflow, permission-matrix, or multi-flag control flow (the State-Machine Verification Gate would run with full rigor).
- **Base context beyond direct local reads:** a finding's correctness depends on base behavior that `git show <base>:<path>` + `rg` or local file reads cannot settle (mandatory SCSI base-context).
- **Live UI/runtime evidence needed:** the diff changes UI, runtime behavior, or browser-visible flows where local static reads cannot prove the finding or fix.

If any trigger holds, stop and escalate to `~/.agents/skills/k-review/SKILL.md` (its Role Detection owns the authorship procedure);
do not edit code here. If a trigger surfaces mid-pass, stop and switch to `k-review` rather than half-doing the heavy machinery.

## Workflow (agent-assisted verify and fix in place)

1. **Scope.**
   Inspect `git status --porcelain=v1 -b` and the diff (`git diff`, `git diff --staged`, or `git diff <range>` / `git log --oneline <range>`).
   If there are no diffs, say so and stop.
2. **Base context (opt-in).** Default off.
   Establish base context when a finding's correctness genuinely depends on how base behaves today;
   use the most direct sufficient source (`git show <base>:<path>` + `rg`, or local file reads).
   Do not omit needed base context because SCSI would be heavier; escalate to `k-review` when direct local reads are not enough.
3. **Candidate audit.**
   Launch one read-only `change-auditor` worker when the harness supports subagents;
   otherwise run the same read/judge pass inline and report `agent_lane=inline-degraded`.
   The worker returns candidate findings and proposed fixes only; the parent owns edits.
4. **Controller findings audit.**
   Inline the Findings-Set Audit from `judging_core.md` over the candidate set:
   remove duplicates, unsupported claims, gaps, overengineering, and unactionable fixes before adversarial work.
   Report `findings_audit=inline`.
5. **Final adversarial refutation.**
   If the audited candidate set is empty, skip adversarial work and report `Adversarial verification: skipped (no candidates after findings audit)`.
   Otherwise, run `adversarial-verifier` over the audited candidate set when the harness supports it;
   if not, run the Candidate Refutation Ladder inline and report `adversarial=inline-degraded`.
   No finding may be fixed or reported until it survives this final pass.
   If a fix here reopens findings and a further round is warranted, hand off to `~/.agents/skills/k-converge/SKILL.md` rather than looping ad hoc.
6. **Fix survivors.**
   Apply the Verify-and-Fix Loop's fix, quality-gate, and Post-Review Stage steps from `judging_core.md` over the surviving findings.
   The **Post-Review Lens (The Four Dimensions)** and **Post-Review Stage** are foregrounded for this skill.
   Do not commit or push unless explicitly asked.

## Output

- Findings: what was found, what was fixed, what was verified (ordered by severity).
- Mechanical gates: what was run, pass/fail.
- Post-review: hygiene findings on the fix diff (by dimension) and how they were resolved.
- Remaining: anything not fixed (and why), plus any escalation recommendation.
- `Compatibility impact: none | removed (requested) | kept existing (requested)`.
