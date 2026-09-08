# Produce a Requested Fix

Diagnosis alone reports the cause and evidence; implement only when the user requested a fix.
Use the settled cause, scoped targets, and intended/preserved behavior to produce the fix and regression cases.
Load `~/.agents/skills/k-code-quality-tests/SKILL.md` when writing the regression cases.
Do not expand into sibling cleanup, a redesign, or an additional architecture workflow automatically.
Remove task-local temporary instrumentation during Produce; preserve required observability and unrelated user changes.
Integrate and format before one final Verify stage.
The root's final plan covers the original reported scenario, the targeted regression, preserved behavior and any required performance comparison.
Reuse one check when it covers multiple criteria; do not repeat the same scenario under different step names.
Run planned checks once; report failed/blocked conditions without an automatic repair loop or post-review stage.
Missing runtime access remains blocked, not a passed check inferred from source.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Use the implementation band for substantial settled edits and keep the strong root on decisions/context integration.
Keep strong research and final judgment where required by risk. Honor an explicit no-delegation request inline.
