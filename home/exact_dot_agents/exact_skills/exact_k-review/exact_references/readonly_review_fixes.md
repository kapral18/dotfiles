# Review Fixes

Fix findings within the current packet's write scope and the approved semantic delta (see `~/.agents/skills/k-review/references/authorship.md` for resolving write scope); a final-Verify-stage packet stays read-only by category and reports instead.
For `other`/`unknown` authorship, the artifact is not yours to write regardless of packet category —
fixing still requires the user to explicitly say to fix it.
Gather the known finding/thread batch in Understand, retaining source evidence and decisions.
Use implementation-band workers for substantial settled edits during Produce; each returns artifacts without private checks.
Do not broaden into missing features, unrelated hygiene, or another finder pass.
Integrate tests, docs, generated outputs, and formatting before one final Verify stage over the complete fix batch.
Run the planned checks once and use one strong final judgment where needed.
The root applies SOP §3.5 to authorized recovery; this reference grants no repair authority or separate recheck loop.
Commit, push, reply, resolve, and publish only under their existing explicit or bounded authority.

## Fix Scope (Mandatory Boundary)

A fix stays inside the behavior the reviewed diff already changes.
It becomes a proposal instead — reported with the smallest change and left unapplied —
when it would need a new user-visible state (loading, error, retry), a new prop or export on a component outside the diff's package, a file outside the packages the diff touches, or new translated strings beyond the changed component.
A review that finds a defect it cannot fix inside that scope reports the defect; it does not build the feature.

This boundary exists because a review defect once became an unbounded 2.5-hour feature build:
three redesigns, a shared-component API change, six full-suite runs, and a dead session with 11 uncommitted files.
The fix pass in this reference is one round: fix the in-scope findings, then one final judgment over the fix diff.
A finding that judgment raises against the fix is ordinary SOP §3.5 recovery when it stays inside Fix Scope (repair, rerun the affected checks, stop under §3.4); outside Fix Scope it is a proposal for the user.
Neither is a fresh refutation round.

**`k-converge` is the only unbounded loop.**
Its declared exit condition (`~/.agents/skills/k-converge/SKILL.md` Step 1) is the named exception to this bound and to SOP §3.5's "Only the active root/main session owns stage transitions; skills supply task mechanics and criteria, never nested lifecycles" — enter it only by explicit user invocation or the caller's authorized handoff under its workflow-handoff contract, never by re-running this reference's fix pass as a substitute for its refutation rounds.
