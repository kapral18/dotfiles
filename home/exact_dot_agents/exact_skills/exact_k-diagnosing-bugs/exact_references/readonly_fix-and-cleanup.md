# Fix a Diagnosed Bug

Diagnosis alone reports the cause and evidence; implement only when the user asked for a fix.

- Use the settled cause, scoped targets, and intended and preserved behavior to write the fix and its regression cases.
  Load `~/.agents/skills/k-code-quality-tests/SKILL.md` for the regression cases.
- Do not expand into sibling cleanup or a redesign.
- Remove temporary instrumentation; keep required observability and unrelated user changes.
- Run the checks once on the finished fix: the original reported scenario, the regression case, preserved behavior, and any needed performance comparison.
  One check may cover several criteria; do not repeat a scenario under different names.
- On a failure, fix within scope and rerun the affected checks. After two attempts without new evidence, stop and report.
- Missing runtime access is a blocked check, never a pass inferred from source.
