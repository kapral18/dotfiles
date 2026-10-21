---
name: k-light-review
description: "Use for one quick inline review of a small, low-risk, self-authored local change."
---

# Light Review

## Light-Eligibility Predicate

All conditions must hold: local-only diff, verified self-authorship, reversible change, focused observable check, and semantically simple behavior.
Unknown is not eligible.
PR context, explicit full/deep review, a `~/AGENTS.md` §3 step 5 trigger, deletion or replacement, stateful or workflow behavior,
or required base/runtime investigation excludes the light path.
Do not treat a small diff or the absence of test failures as low-risk proof.

## Review

Review inline, once.
Resolve the diff and authorship (`~/.agents/skills/k-review/references/authorship.md`); local does not mean self-authored.

- Read the full diff and the enclosing files; check callers when a changed signature or contract has them.
- Judge correctness, preserved behavior, and completeness with the Truth Validation Framework and Candidate Refutation Ladder in `~/.agents/skills/k-review/references/judging_core.md`.
- De-slop the change: load `~/.agents/skills/k-code-quality/SKILL.md` and apply its De-slop section.
- Also report defects in the change's impact (`~/AGENTS.md` §3 step 1), collecting its impact list with `k-behavior-map` (before a change) when none exists.
- Reuse check results already run; do not repeat them.
- Fix supported findings in the same pass when authorship gives write scope; otherwise report them.
- If an excluding trigger appears while reading, stop and switch: a `~/AGENTS.md` §3 step 5 trigger to `k-review` Verify mode,
  any other to `k-review` local changes mode.

Commit, push, and publish only as `~/AGENTS.md` §5 allows.

## Output

Anchored findings with evidence, fixes applied, check results, and anything left unverified.
