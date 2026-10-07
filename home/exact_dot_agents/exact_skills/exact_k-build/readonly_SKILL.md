---
name: k-build
description: "Manual-only recipe to implement an approved spec inline, with tests and docs, and one check run on the finished change."
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
- Write tests and docs with the change, regenerate generated outputs, and format.
- Update every co-edit-set member in the impact map. A consumer left unchanged needs evidence that it is unaffected.
- If a discovery invalidates the approved approach, stop and bring the concrete decision to the user instead of silently changing scope.

## Verify

- Run the planned checks once on the finished change, cheap prerequisites first. Keep full logs and the real exit status.
- Run visual or runtime checks only for criteria that need them, with a verified target:
  load `k-ui-capture` and the matching domain overlay.
  Windows coverage only when asked, through `k-live-ui-windows`.
- On a failure, fix within scope and rerun the failed and affected checks.
  After two attempts without new evidence, stop and report the blocker.
- Run the independent review that `~/AGENTS.md` §4 requires through `k-review` verify mode.

## Output

The change summary, each criterion as passed, failed, or blocked with evidence, open decisions, and compatibility impact.
Nothing is committed, pushed, or published without its own request.
