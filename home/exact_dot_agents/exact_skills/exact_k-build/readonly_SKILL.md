---
name: k-build
description: "Manual-only recipe to implement an approved spec inline, with necessary checks and one verification run on the finished change."
disable-model-invocation: true
---

# Build

Implement the approved `k-spec` plan inline.

## Scope and authority

- Read the plan and its approval. Do not ask again when the user already approved implementation.
- Missing material intent goes back through `k-spec`; a clear approved request needs no extra approval step.
- Approval covers working-tree edits, needed generation or setup, and the checks. It does not cover commits, pushes, or publication.
- Keep the plan's out-of-scope list binding.

## Implement

- Follow the plan's dependency order; do not assume two edits are independent just because they touch different files.
- Ensure minimum sufficient test protection under `~/AGENTS.md` §3 alongside the implementation;
  update affected docs and generated outputs, then format.
- Update every co-edit-set member in the impact map. A consumer left unchanged needs evidence that it is unaffected.
- If a discovery invalidates the approved approach, stop and bring the concrete decision to the user instead of silently changing scope.

## Verify

- Run the planned checks once on the finished change, cheap prerequisites first. Keep full logs and the real exit status.
- Run a live check (`~/AGENTS.md` §3 step 4) only when the user asks for it, with a verified target and a hard time limit;
  for a visual or runtime one, load `k-ui-capture`, plus the matching domain overlay when one exists.
  Windows coverage only when asked, through `k-live-ui-windows`.
- On a failure, fix within scope and rerun the failed and affected checks.
  After two attempts without new evidence, stop editing and investigate read-only;
  report the blocker only if that investigation cannot resolve it.
- Run the independent review that `~/AGENTS.md` §3 step 5 requires through `k-review` verify mode.

## Output

The change summary, each criterion as passed, failed, blocked, or unverified (only a live check would settle it;
`~/AGENTS.md` §3 step 8) with evidence, open decisions, and compatibility impact.
Commit, push, and publish only as `~/AGENTS.md` §5 allows.
