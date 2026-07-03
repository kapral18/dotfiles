---
sidebar_position: 3
title: "Get your changes reviewed"
---

# Get your changes reviewed

Three rungs, same judging engine, increasing independence. Start at the lightest that fits and escalate — the flows themselves tell you when.

**Prerequisites:** a session in the repo with the changes (uncommitted, staged, a branch, or a PR number).

## Rung 1 — `/light-review`: your own low-risk changes, fixed in place

```text
/light-review
```

The agent walks your diff against the full coverage checklist (security, correctness, data-loss, perf, tests, docs), **fixes findings directly in the working tree**, runs the repo's lint/type/tests, then audits its own fixes with the four-dimension hygiene lens (redundancy, verbosity, semantic + logical duplication, gaps). Output: findings → what was fixed → gates run → anything remaining.

It will refuse and point up a rung when the target is a PR, someone else's code, or risky/stateful territory — that's the built-in escalation, not an error.

## Rung 2 — full `review`: PRs, others' code, risky changes

```text
review PR #4321
```

or for local work that needs base-branch context: `review my branch against main`.

What you get that rung 1 doesn't: exhaustive PR context intake (every comment thread, linked issue, CI check — read in full, not previews), base-branch verification (what does `main` actually do today), and for stateful logic a disposable verification harness under `/tmp`. On your own PR it can apply fixes; on someone else's it drafts comments and **never posts without showing you the exact payload first** — publication is always human-gated.

## Rung 3 — `/agent-review`: independent lanes + adversarial verification

```text
/agent-review PR #4321
```

The controller launches several reviewer subagents in parallel (each with a different focus — correctness, tests, security…), plus a blind "fresh eyes" lane that sees zero PR context, then sends every candidate finding to a **different-family model whose only job is to refute it**. Findings that survive get a live UI check when the diff touches one. Expect a structured report: roster, verdict counts (`confirmed/refuted/undecidable`), kept/dropped findings with reasons, and draft comments awaiting your go-ahead.

Use it when the change is risky enough to fund five readers; it costs accordingly.

## Reading any review's output

- Findings are ordered by severity; each carries evidence (file:line, command output) — no evidence, no finding.
- `Compatibility impact:` line tells you if behavior was removed/kept — it must say `none` unless you asked otherwise.
- "Post-review: clean" means the review's own fixes were audited too.

## Pivots from here

- Review found an architectural smell → hand it to `codebase-design` ("design a better seam for this").
- Review found a bug worth its own work → `draft an issue from finding 2`.
- A finding needs a live browser check → the agent does this itself in rungs 2–3; in rung 1 just ask `verify this in the browser`.
