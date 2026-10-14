# Review Fixes

Fix findings only within write scope (`~/.agents/skills/k-review/references/authorship.md`).
For `other` or `unknown` authorship, fixing needs the user to explicitly say so.

## Fix Scope (Mandatory Boundary)

A fix stays within the authorized request and the behavior under review, including omitted requirements and their necessary callers, tests, and docs.
An incomplete diff does not narrow that scope: a requested error state or a required caller in another package is still in scope.
New behavior, redesigns, or unrelated cleanup outside the request are proposals: report the smallest change and leave it unapplied.

## Step back first

Before each fix round, check the work as its orchestrator, not as the next finding's fixer.
This adds no stop or cap; the Fix procedure owns those.

- Restate the user's goal in their words. Check each finding, and each planned fix, against that goal.
- Fix a finding the task change caused or the request covers.
  List one that held at the task-start state and the request does not cover under `Proposed:`.
- When a fix would add another special case, or the last fixes caused the new findings, prefer a simpler fix within the request:
  replace the approach, or revert this task's change that drifted from the goal, with the fixes only it needed.

## Fix procedure

1. In Verify mode, before each fix round, copy the files it will touch to a fresh scratch directory.
   If a fix needs another existing file, copy it before editing it.
2. Fix the supported findings together, low ones too, within write scope and Fix Scope.
3. Rerun only failed and affected checks, exercise changed behavior, and update touched behavior-map entries.
4. Outside Verify mode, read the fix diff once. Repair an in-scope problem it reveals and rerun affected checks, then stop.
5. In Verify mode, form the fix diff with `diff -uN <copy> <file>` for each touched file; `-N` includes new files.
   Launch one reviewer using the Reviewer launch procedure in `~/.agents/skills/k-review/SKILL.md`; it reviews only this fix diff.
   Give it the user's request in their words, the findings being fixed, rerun checks, `Open:` items, and rejected and proposed findings.
   Skip this review only for wording-only fixes (typos, reflow, a rename with no change in meaning).
6. In steps 6 to 8, a finding counts only when this task fixes it (Step back first);
   one listed under `Proposed:` does not continue the loop.
   Repeat the reviewed fix round while the last fix-diff review found a supported medium or higher finding;
   fix lows in the same round without another review.
   Stop after three fix-diff reviews in this full round.
   A returned cause is a finding with the same trigger in the same function or rule as one an earlier round fixed.
   Investigate it read-only first, then fix it with the concrete cause you found.
   If it returns a second time, stop the loop and list it under `Open:`, with the attempts and what the investigation found as its blocker.
   A reviewer repeating a finding you rejected is not a returned cause: reject it again, unless it names new evidence;
   then check it like any finding.
   Still fix every other supported finding of the last review with steps 2 and 3.
7. If this round's two full reviewers found a supported medium or higher finding, run another full round without asking:
   two fresh reviewers on the whole Verify scope as it stands now, given every finding fixed, rejected, or proposed so far, reporting only new ones.
   Fix its findings with steps 1 to 6. A clean fix-diff review does not end the loop; a clean full round does.
   Stop when a full round finds no new supported medium or higher finding (fix its lows), after three full rounds,
   or when a cause returns a second time.
8. Mark each fix after the last review that is not wording-only "(unreviewed)" in `Checked:`, and list any finding you could not fix under `Open:` with its blocker.
   Report what was fixed, rejected, proposed, and left open.
   If the loop stopped at a cap while the last full round found a new medium or higher finding, or with such a fix unreviewed,
   say the review did not reach a clean round and end with `Decision needed:` another Verify round, with your pick.
After two attempts at the same failure without new evidence, stop editing and investigate read-only or report the blocker.
Commit, push, reply, resolve, and publish only as `~/AGENTS.md` §5 allows.
