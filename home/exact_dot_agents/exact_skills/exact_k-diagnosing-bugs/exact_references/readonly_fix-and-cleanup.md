# Fix and cleanup

## Phase 5 — Fix + regression test

This phase is fix work (SOP §1): on an assessment request, stop after Phase 4 with the verified cause and proposed fix.
Write the regression test **before the fix**, but only if there is a **correct seam** —
one where the test exercises the real bug pattern as it occurs at the call site. A too-shallow seam gives false confidence.
**If no correct seam exists, that itself is the finding** — the architecture prevents lockdown;
hand it to `~/.agents/skills/k-codebase-design/SKILL.md`.
If a correct seam exists: turn the minimised repro into a failing test, watch it fail (revert the fix in place —
see `k-code-quality-tests`), apply the fix, watch it pass, then re-run the Phase 1 loop on the original scenario.
For stateful/branch-heavy fixes, verify against base behaviour buckets with the SOP state-machine verification harness.

## Phase 6 — Cleanup + post-mortem

Before declaring done:

- Original repro no longer reproduces (re-run the Phase 1 loop).
- Regression test passes (or absence of seam is documented).
- Defect-class sweep: enumerate the class of defect the root cause implies, then sweep the codebase (and sibling repos when the class spans them) for other instances; classify every hit as fixed, out-of-scope (say where it goes), or clean.
  Fix instances beyond the reported bug only when the user asked for a class-wide fix; otherwise list them as findings.
  A fix for instance N is not complete while unexamined siblings remain.
- All `[DEBUG-...]` instrumentation removed (grep the prefix).
- Throwaway prototypes deleted or clearly marked.
- The correct hypothesis is stated in the commit / PR message so the next debugger learns.

Then ask: **what would have prevented this bug?**
If the answer is architectural (no good seam, tangled callers, hidden coupling), hand off to `k-codebase-design` with specifics —
after the fix is in.
