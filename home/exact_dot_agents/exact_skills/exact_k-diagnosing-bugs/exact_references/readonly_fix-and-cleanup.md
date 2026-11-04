# Fix a Diagnosed Bug

Use the task's fix authority under `~/AGENTS.md` §1; diagnosis grants no additional edit authority.

- Use the settled cause, scoped targets, and intended and preserved behavior to write the fix.
  Reuse the reproduction for diagnosis, and ensure minimum sufficient test protection under `~/AGENTS.md` §3 and `~/.agents/skills/k-code-quality-tests/SKILL.md`.
  Reuse existing coverage; add a test only when its distinct protection earns its maintenance cost.
  Repeated test-only repairs call for simplification or removal under that rule.
- Do not expand into sibling cleanup or an unrelated redesign.
- Remove temporary instrumentation; keep required observability and unrelated user changes.
- Run the smallest sufficient checks once on the finished fix for the reported failure and material preserved behavior (`~/AGENTS.md` §3 step 4).
  For slowness, rerun the diagnosis micro-benchmark once against the fix.
  One check may cover several criteria; do not repeat a scenario under different names.
- On a failure, fix within scope and rerun the affected checks. After two attempts at the same failure without new evidence,
  stop editing and investigate read-only; report the blocker if it cannot be resolved.
- Report an unresolved runtime criterion under `Open:`, with the missing evidence or check as its blocker
  (`~/AGENTS.md` §3 step 8), never as a passed `Checked:` item.
