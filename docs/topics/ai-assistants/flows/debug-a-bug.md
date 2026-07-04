---
sidebar_position: 4
title: "Debug a hard bug"
---

# Debug a hard bug

For bugs where the cause isn't obvious from the stack trace. The discipline is: **no theorizing until a red loop exists** — a fast command that fails on exactly your symptom.

**Prerequisites:** a session in the repo; ideally your reproduction notes (what you did, what you saw).

## Start it

```text
debug this: `todo.py list` crashes with "TypeError: string indices must be integers" when the db file came from the old version
```

Give the exact symptom text and how you triggered it. The `diagnosing-bugs` skill fires on "debug/diagnose/broken/flaky/slow".

## What happens, phase by phase

1. **Loop first.** The agent's whole initial effort goes into one command that goes red on your bug — a failing test, a curl, a CLI call with a fixture. You'll see it _run it and show the red output_ before any theory:

   ```text
   $ printf '["legacy"]' > /tmp/db.json && TODO_DB=/tmp/db.json python3 todo.py list
   TypeError: string indices must be integers   ← red, reproduces your symptom
   ```

   If it genuinely can't build one, it stops and asks you for exactly one of: env access, a captured artifact (HAR/log/dump), or permission to add temporary instrumentation. That question is the flow working, not failing.

2. **Minimize.** The repro is shrunk until every element is load-bearing.
3. **Hypotheses — you can help here.** It lists 3–5 ranked, falsifiable causes, each with a negative control (an input the explanation calls irrelevant that must not change the verdict). A confident rationale is still only a hypothesis: the red-to-green loop and the control are the proof. If you know the codebase, re-rank with one line ("it's #3, we changed the loader last week"); if you're away, it proceeds with its own ranking.
4. **Probe, fix, regression-test.** Test written _before_ the fix where a proper seam exists; then the original (un-minimized) scenario is re-run to prove your actual symptom is gone.
5. **Cleanup.** All `[DEBUG-…]`-tagged instrumentation removed, correct hypothesis stated in the commit message.

## What to expect in the final report

- The red-loop command and its now-green run (before/after, pasted).
- The confirmed hypothesis and the discarded ones.
- The regression test path — or, importantly, the finding that **no correct seam exists** to lock the bug down.

## Pivots from here

- "No correct seam" or the post-mortem answer to _what would have prevented this?_ is architectural → say `hand this to codebase-design` — that's the built-in escalation.
- The fix deserves scrutiny → `/light-review` ([review flow](review-your-changes.md)).
- The bug should be recorded, not fixed now → `draft an issue from the repro`.
