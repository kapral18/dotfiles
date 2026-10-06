---
name: k-light-review
description: "Use for one quick inline review of a small, low-risk, self-authored local change."
---

# Light Review

## Light-Eligibility Predicate

All conditions must hold: local-only diff, verified self-authorship, reversible change, focused observable check, and semantically simple behavior.
Unknown is not eligible.
PR context, explicit full/deep review, security/auth/crypto, persisted data, public API, deletion/replacement, stateful/parser/workflow behavior, or required base/runtime investigation excludes the light path.
Do not treat a small diff or the absence of test failures as low-risk proof.

## Review

Review inline, once.
Resolve the diff and authorship (`~/.agents/skills/k-review/references/authorship.md`); local does not mean self-authored.

- Read the full diff and the enclosing files; check callers when a changed signature or contract has them.
- Judge correctness, preserved behavior, and completeness with the Truth Validation Framework and Candidate Refutation Ladder in `~/.agents/skills/k-review/references/judging_core.md`.
- Reuse check results already run; do not repeat them.
- Fix supported findings in the same pass when authorship gives write scope; otherwise report them.
- If a risk trigger appears while reading, stop and switch to `k-review` local changes mode.

Do not commit, push, or publish without an explicit request.

## Output

Anchored findings with evidence, fixes applied, check results, and anything left unverified.
