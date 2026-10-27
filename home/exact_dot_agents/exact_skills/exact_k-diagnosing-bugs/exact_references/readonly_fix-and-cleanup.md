# Fix a Diagnosed Bug

Diagnosis alone reports the cause and evidence; implement only when the user asked for a fix.

- Use the settled cause, scoped targets, and intended and preserved behavior to write the fix and its regression cases.
  Load `~/.agents/skills/k-code-quality-tests/SKILL.md` for the regression cases.
- Do not expand into sibling cleanup or a redesign.
- Remove temporary instrumentation; keep required observability and unrelated user changes.
- Run the checks once on the finished fix: the regression case, preserved behavior, and the reported scenario as a local run that ends on its own (`~/AGENTS.md` §3 step 4).
  For slowness, rerun the diagnosis micro-benchmark once against the fix.
  One check may cover several criteria; do not repeat a scenario under different names.
- On a failure, fix within scope and rerun the affected checks. After two attempts at the same failure without new evidence,
  stop editing and investigate read-only; report the blocker if it cannot be resolved.
- Report an unresolved runtime criterion under `Open:`, with the missing evidence or check as its blocker
  (`~/AGENTS.md` §3 step 8), never as a passed `Checked:` item.
