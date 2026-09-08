---
sidebar_position: 4
title: "Debug a hard bug"
---

# Debug a hard bug

For bugs where the cause is not obvious from the stack trace. Diagnose from source and observed failure evidence; use a focused reproduction when it resolves a material uncertainty. A runnable reproduction is not a prerequisite for reading source.

**Prerequisites:** a session in the repo; ideally your reproduction notes (what you did, what you saw).

## Start it

```text
debug this: `todo.py list` crashes with "TypeError: string indices must be integers" when the db file came from the old version
```

Give the exact symptom text and how you triggered it. The `k-diagnosing-bugs` skill fires on "debug/diagnose/broken/flaky/slow".

## What happens

1. **Understand the failure.** Resolve the affected version/path and expected-versus-observed behavior. Reuse complete logs, traces and existing failing-test evidence. Run a targeted baseline only when needed to distinguish the reported failure.
2. **Distinguish causes.** Read relevant source and choose probes that settle competing explanations. Minimize only when useful; there is no hypothesis quota or requirement to prove every fixture element indispensable. Intermittent failures use an explicit sampling plan and stopping condition, not an endless stress loop.
3. **Produce an authorized fix.** A diagnosis-only request stops with evidence and a proposed fix. When a fix is requested, strong research settles the cause/design and the implementation band makes substantial edits, regression cases and docs. The explicit no-delegation exception stays inline. Remove temporary instrumentation before final verification.
4. **Verify once.** The root freezes the integrated candidate and runs the deduplicated final checks, including the original reported scenario and preserved behavior. Necessary strong review/refutation and applicable UI evidence belong to this same stage. Workers do not run private QA, and a failure does not automatically restart implementation.

Source evidence can establish a defect without reproducing its runtime symptom. The report must distinguish those conclusions: unavailable runtime evidence remains blocked, never passed. Ask for access or a missing artifact only when it blocks the requested conclusion and safe local investigation cannot resolve it.

## What to expect in the final report

- The cause and original symptom with source/tool anchors, relevant ruled-out alternatives, and uncertainty.
- The baseline and final check receipts when those checks ran; a precise blocker otherwise.
- For an authorized fix: changed paths, regression coverage, preserved behavior and compatibility impact. No commit is implied.

## Pivots from here

- A necessary in-scope seam/design question uses `k-codebase-design` during Understand; it does not trigger an automatic post-fix redesign.
- Choose the appropriate [review scope](review-your-changes.md) for final Verify before entering it; do not append another review after the fix has already been verified.
- The bug should be recorded, not fixed now → `draft an issue from the repro`.
