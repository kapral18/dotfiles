# Review Fixes

Before reviewing a fix, load `~/.agents/skills/k-review/references/adversarial_stance.md`; reuse it if already loaded in full.

Fix findings only within write scope (`~/.agents/skills/k-review/references/authorship.md`).

## Fix Scope (Mandatory Boundary)

A fix stays within the authorized request and the behavior under review, including omitted requirements and their necessary callers, tests, and docs.
An incomplete diff does not narrow that scope: a requested error state or a required caller in another package is still in scope.
It also covers defects in the change's impact (`~/AGENTS.md` §3 step 1), even ones that predate the task.
New behavior, redesigns, or unrelated cleanup outside the request and that impact are proposals:
report the smallest change and leave it unapplied.
A follow-up `~/AGENTS.md` §1 puts in the request's scope is not a proposal: fix it.

## Step back first

Before each fix round, check the work as its orchestrator, not as the next finding's fixer.
This adds no stop; the Fix procedure owns the stopping rule.

- Restate the user's goal in their words. Check each finding, and each planned fix, against that goal.
- Fix a finding the task change caused, the request's scope (`~/AGENTS.md` §1) covers, or the change's impact holds.
  List one that held at the task-start state outside all three under `Proposed:`.
- Before editing, collect the impact list of the planned fixes (`k-behavior-map`, before a change):
  every consumer and copy of each rule or function they touch, and every trigger earlier rounds raised on that rule or function.
  Read those files first, and check each fix against all of them before the next review.
- Before adding another special case, apply the feasibility gate in `~/AGENTS.md` §3 step 2.
  Do not extend an approach whose required enforcement assumption has failed:
  replace it within scope or revert this task's change that drifted from the goal.
  Remove superseded exception logic and unused scaffolding without dropping required product behavior;
  retain or remove tests by `~/AGENTS.md` §3's test-value rule.

## Fix procedure

1. In Verify mode, before each fix round, copy the files it will touch to a fresh directory under `/tmp`.
   If a fix needs another existing file, copy it before editing it.
   Remove these copies as soon as their dependent reviews finish, under `k-cleanup`.
2. Fix the supported findings together, low ones too, within write scope and Fix Scope.
   Fix the class, not the instance: when a finding can recur elsewhere (a copied rule, the same pattern), find every occurrence and fix them all,
   and remove copies when one source can serve; a copy outside Fix Scope goes under `Proposed:`.
3. Rerun only failed and affected checks, exercise changed behavior in a local run that ends on its own (`~/AGENTS.md` §3 step 4),
   and update touched behavior-map entries.
4. Outside Verify mode, read the fix diff once. Repair a problem it reveals within Fix Scope and rerun affected checks, then stop.
5. In Verify mode, form the fix diff with `diff -uN <copy> <file>` for each touched file; `-N` includes new files.
   Launch one reviewer using the Reviewer launch procedure in `~/.agents/skills/k-review/SKILL.md`; it reviews only this fix diff.
   Checkpoint acceptance with `,task review --session <id>` as in Verify mode.
   Give the reviewer the request, acceptance snapshot, original failure cases being fixed, rerun checks, and `Open:` items.
   Give earlier findings and dispositions through the separate history file: assess source first, then reconcile before returning.
   Require a fix result with evidence for each original trigger; reconcile new supported defects too.
   Skip this review only for wording-only fixes (typos, reflow, a rename with no change in meaning).
6. In steps 6 to 8, a finding counts only when this task fixes it (Step back first);
   one listed under `Proposed:` does not continue the loop.
   Repeat the reviewed fix round while the last fix-diff review found a supported finding this task fixes, lows included.
   A returned cause repeats the same specific invariant violation or failed enforcement assumption in the same mechanism as an earlier fix.
   Different inputs, symptoms, locations or finding IDs do not make it a new cause.
   Do not add another input-specific exception: investigate the shared assumption read-only, then replace the approach or revert this task's change there (Step back first).
   Check the result against every earlier trigger and affected consumer of that mechanism.
   If it returns a second time, park it (below), unless a later review names new evidence; then check it like any finding.
   Churn stop: a regression is a supported finding of any severity that a review traces to an edit this fix loop made,
   not a fix that misses its original trigger and not one an earlier review reported.
   A mechanism churns when two reviews each find a regression in it, with no two-reviewer round between them that found none there.
   At the first churn in a mechanism, replace the approach there within Fix Scope (Step back first) and continue.
   A mechanism gets one replacement: the replacement clears its earlier regressions, and its next churn parks it.
   Parking: a parked cause or mechanism no longer continues the loop or blocks its end; the loop goes on for every other finding.
   Report each parked finding under `Decision needed:` with its cause or mechanism, the `Rounds:` trend, and your pick of:
   replace the approach again, revert this task's change there, or leave it open.
   A reviewer repeating a finding you rejected is not a returned cause: reject it again, unless it names new evidence;
   then check it like any finding.
7. If the two-reviewer round found a supported medium or higher finding, run another two-reviewer round without asking:
   two fresh reviewers using the complementary focuses and source-first/history-reconciliation packet in Verify mode, reporting only new findings or resolved findings contradicted by new evidence.
   That next round is narrowed: it reviews what fixes since the previous two-reviewer round touched and their consumers.
   Once a narrowed round finds no new supported medium or higher finding, the next round covers the whole Verify scope.
   Fix its findings with steps 1 to 6.
   A clean fix-diff review or a clean narrowed round does not end the loop before a whole-scope round closes the rounds (below).
   No count of reviews or rounds stops the loop, and it never pauses to ask whether to continue;
   a parked cause or mechanism (step 6) goes to the user only in the final report.
   A whole-scope round with no new supported medium or higher finding and passing evidence for the applicable criteria and claimed fixes closes the rounds;
   fix its lows with steps 1 to 6.
   The loop ends only when reviews have covered every edit that is not wording-only and every supported finding this task fixes from those reviews is fixed or parked (step 6),
   or when every remaining step is blocked by something you cannot clear (step 8):
   no finding this task fixes is left unfixed unless its fix is blocked or it is parked (step 6), and each fix still unreviewed has a blocked review.
   A material unverified result stays `Open:` with its blocker; missing reviewer coverage is returned to that reviewer for completion, not treated as clean.
   Neither checklist membership nor a reviewer's focus may exclude a new supported defect in scope or impact.
   Keep rounds short: aim for about 3 minutes per reviewer and 5 per round. Time a round from launch to results with `date +%s`
   just before the launch and when the results arrive, and a reviewer with the duration the harness reports, if any.
   When a round runs over, or two rounds in a row find the same kind of problem, write one line before the next round:
   what cost the time, and what the next round does differently.
8. Never end your turn before the loop ends (`~/AGENTS.md` §3 step 8).
   In the final report, `Open:` holds only items a blocker you cannot clear stops, each with that blocker,
   such as a material unverified result (step 7) or a fix whose review cannot run (`Review of <fix>: <blocker>`).
   Report fixed findings as a count, each rejected one with a one-line reason, proposed and open items, a `Decision needed:` for each parked cause or mechanism (step 6), and the rounds as a trend:
   `Rounds: <n> (<findings per round>; <total minutes>)` on one line, with minutes from those timings, never estimated; no per-round table.

After two attempts at the same failure (`~/AGENTS.md` §3), in Verify mode continue with step 6 (replace, revert, or park);
report a blocker only when you cannot clear it.
Commit, push, reply, resolve, and publish only as `~/AGENTS.md` §5 allows.
