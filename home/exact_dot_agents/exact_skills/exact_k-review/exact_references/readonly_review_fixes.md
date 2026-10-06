# Review Fixes

Fix findings only within write scope (`~/.agents/skills/k-review/references/authorship.md`).
For `other` or `unknown` authorship, fixing needs the user to explicitly say so.

## Fix Scope (Mandatory Boundary)

A fix stays inside the behavior the reviewed diff already changes.
It becomes a proposal instead — reported with the smallest change and left unapplied — when it would need:

- a new user-visible state (loading, error, retry)
- a new prop or export on a component outside the diff's package
- a file outside the packages the diff touches
- new translated strings beyond the changed component

A defect that cannot be fixed inside this scope is reported, not built.
Out-of-scope fixes grow into unbounded feature work: redesigns, shared API changes, and repeated full-suite runs.

## One round

1. Fix the in-scope findings together, with tests and docs.
2. Run the affected checks once.
3. Re-read the fix diff once.
   A problem it reveals inside Fix Scope gets one more repair and a rerun of the affected checks;
   outside Fix Scope it is a proposal for the user.
4. Stop. Report what was fixed, what was proposed, and what remains.

After two attempts at the same failure without new evidence, stop and report the blocker.
NEVER start another finder or review pass on your own.
Commit, push, reply, resolve, and publish only under their own explicit authority.
