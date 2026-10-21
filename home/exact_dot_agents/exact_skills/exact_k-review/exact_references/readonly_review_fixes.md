# Review Fixes

Fix findings only within write scope (`~/.agents/skills/k-review/references/authorship.md`).
For `other` or `unknown` authorship, fixing needs the user to explicitly say so.

## Fix Scope (Mandatory Boundary)

A fix stays within the authorized request and the behavior under review, including omitted requirements and their necessary callers, tests, and docs.
An incomplete diff does not narrow that scope: a requested error state or a required caller in another package is still in scope.
It also covers defects in the change's impact (`~/AGENTS.md` §3 step 1), even ones that predate the task.
New behavior, redesigns, or unrelated cleanup outside the request and that impact are proposals:
report the smallest change and leave it unapplied.

## Step back first

Before each fix round, check the work as its orchestrator, not as the next finding's fixer.
This adds no stop; the Fix procedure owns the stopping rule.

- Restate the user's goal in their words. Check each finding, and each planned fix, against that goal.
- Fix a finding the task change caused, the request covers, or the change's impact holds.
  List one that held at the task-start state outside all three under `Proposed:`.
- Before editing, collect the impact list of the planned fixes (`k-behavior-map`, before a change):
  every consumer and copy of each rule or function they touch, and every trigger earlier rounds raised on that rule or function.
  Read those files first, and check each fix against all of them before the next review.
- When a fix would add another special case, or the last fixes caused the new findings, prefer a simpler fix within the request (one that removes text rather than adding a clause):
  replace the approach, or revert this task's change that drifted from the goal, with the fixes only it needed.

## Fix procedure

1. In Verify mode, before each fix round, copy the files it will touch to a fresh scratch directory.
   If a fix needs another existing file, copy it before editing it.
2. Fix the supported findings together, low ones too, within write scope and Fix Scope.
   Fix the class, not the instance: when a finding can recur elsewhere (a copied rule, the same pattern), find every occurrence and fix them all,
   and remove copies when one source can serve; a copy outside Fix Scope goes under `Proposed:`.
3. Rerun only failed and affected checks, exercise changed behavior in a local run that ends on its own (`~/AGENTS.md` §3 step 4),
   and update touched behavior-map entries.
4. Outside Verify mode, read the fix diff once. Repair a problem it reveals within Fix Scope and rerun affected checks, then stop.
5. In Verify mode, form the fix diff with `diff -uN <copy> <file>` for each touched file; `-N` includes new files.
   Launch one reviewer using the Reviewer launch procedure in `~/.agents/skills/k-review/SKILL.md`; it reviews only this fix diff.
   Give it the user's request in their words, the findings being fixed, rerun checks, `Open:` items, and rejected and proposed findings.
   Skip this review only for wording-only fixes (typos, reflow, a rename with no change in meaning).
6. In steps 6 to 8, a finding counts only when this task fixes it (Step back first);
   one listed under `Proposed:` does not continue the loop.
   Repeat the reviewed fix round while the last fix-diff review found a supported medium or higher finding;
   fix lows in the same round without another review.
   A returned cause is a finding with the same trigger in the same function or rule as one an earlier round fixed, whatever its wording.
   Do not patch it again: investigate it read-only first, then replace that function or rule's approach or revert this task's change there (Step back first),
   and check the result against every earlier trigger on it and against its consumers.
   If it returns a second time, list it under `Open:`, with the attempts and what the investigation found as its blocker.
   Like a `Proposed:` finding, it then no longer continues the loop, unless a later review names new evidence;
   then check it like any finding.
   The loop goes on for every other finding.
   A reviewer repeating a finding you rejected is not a returned cause: reject it again, unless it names new evidence;
   then check it like any finding.
7. If this round's two full reviewers found a supported medium or higher finding, run another full round without asking:
   two fresh reviewers given every finding fixed, rejected, or proposed so far, reporting only new ones.
   A later full round is narrowed: it reviews what the fixes since the last full round touched and their consumers.
   Once a narrowed round finds no new supported medium or higher finding, a full round covers the whole Verify scope.
   Fix its findings with steps 1 to 6.
   A clean fix-diff review or a clean narrowed round does not end the loop; a clean full round on the whole scope does.
   No count of reviews or rounds stops the loop, and it never pauses to ask whether to continue.
   The loop ends when a full round on the whole scope finds no new supported medium or higher finding; fix its lows.
   Keep rounds short: aim for about 3 minutes per reviewer and 5 per round. Time a round from launch to results with `date +%s`
   just before the launch and when the results arrive, and a reviewer with the duration the harness reports, if any.
   When a round runs over, or two rounds in a row find the same kind of problem, write one line before the next round:
   what cost the time, and what the next round does differently.
8. Mark each fix after the last review that is not wording-only "(unreviewed)" in `Checked:`, and list any finding you could not fix under `Open:` with its blocker.
   Report what was fixed, rejected, proposed, and left open, and the rounds as a trend:
   `Rounds: <n> (<findings per round>; <total minutes>)`, with minutes from those timings, never estimated.

After two attempts at the same failure without new evidence, stop editing and investigate read-only or report the blocker.
Commit, push, reply, resolve, and publish only as `~/AGENTS.md` §5 allows.
