# Review Fixes

Fix findings only within write scope (`~/.agents/skills/k-review/references/authorship.md`).
For `other` or `unknown` authorship, fixing needs the user to explicitly say so.

## Fix Scope (Mandatory Boundary)

A fix stays within the authorized request and the behavior under review, including omitted requirements and their necessary callers, tests, and docs.
An incomplete diff does not narrow that scope: a requested error state or a required caller in another package is still in scope.
New behavior, redesigns, or unrelated cleanup outside the request are proposals: report the smallest change and leave it unapplied.

## Fix procedure

1. In Verify mode, before each fix round, copy the files it will touch to a fresh scratch directory.
   If a fix needs another existing file, copy it before editing it.
2. Fix the supported findings together, low ones too, within write scope and Fix Scope.
3. Rerun only failed and affected checks, exercise changed behavior, and update touched behavior-map entries.
4. Outside Verify mode, read the fix diff once. Repair an in-scope problem it reveals and rerun affected checks, then stop.
5. In Verify mode, form the fix diff with `diff -uN <copy> <file>` for each touched file; `-N` includes new files.
   Launch one reviewer using the Reviewer launch procedure in `~/.agents/skills/k-review/SKILL.md`; it reviews only this fix diff.
   Give it the findings being fixed, rerun checks, known gaps, and rejected findings.
   Skip this review for wording-only fixes: no rule, command, or behavior change.
6. Repeat the Verify fix round until no supported medium or higher finding remains.
   Stop after three fix-diff reviews, or when the same cause at the same place returns.
   After the last review, fix only wording-only lows. Report the rest under `Open:` (medium or higher) or `Known gaps:` (low).
7. Report what was fixed, rejected, proposed, and left open. No second full review without a new user request.

After two attempts at the same failure without new evidence, stop editing and investigate read-only or report the blocker.
Commit, push, reply, resolve, and publish only under their own explicit authority.
