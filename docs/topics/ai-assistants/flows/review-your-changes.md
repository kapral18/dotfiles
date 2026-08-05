---
sidebar_position: 3
title: "Get your changes reviewed"
---

# Get your changes reviewed

Three rungs, same judging engine, increasing independence. Start at the lightest that fits and escalate — the flows themselves tell you when.

**Prerequisites:** a session in the repo with the changes (uncommitted, staged, a branch, or a PR number).

## Rung 1 — `/k-light-review`: your own low-risk changes, fixed in place

```text
/k-light-review
```

The agent walks your diff against the full coverage checklist (security, correctness, data-loss, perf, tests, docs), **fixes findings directly in the working tree**, runs the repo's lint/type/tests, then audits its own fixes with the four-dimension hygiene lens (redundancy, verbosity, semantic + logical duplication, gaps). Output: findings → what was fixed → gates run → anything remaining.

It will refuse and point up a rung when the target is a PR, someone else's code, or risky/stateful territory — that's the built-in escalation, not an error.

## Rung 2 — full `k-review`: PRs, others' code, risky changes

```text
review PR #4321
```

or for local work that needs base-branch context: `review my branch against main`.

What you get that rung 1 doesn't: exhaustive PR context intake (every comment thread, linked issue, CI check — read in full, not previews), base-branch verification (what does `main` actually do today), and for stateful logic a disposable verification harness under `/tmp`. On your own PR it can apply fixes; on someone else's it drafts comments and **never posts without showing you the exact payload first** — publication is always human-gated.

## Rung 3 — `/k-deep-review`: independent lanes + adversarial verification

```text
/k-deep-review PR #4321
```

The controller launches a bounded reviewer roster: one sighted `correctness-regressions` lane for simple single-surface diffs, evidence-triggered extra lanes for independent risk classes, and a blind "fresh eyes" lane only when the diff has comprehension-risk signals. Each lane is a real expert lens with its own checks and, where one exists, its own quality skill — not a generalist told to emphasize a keyword. After lane merge/dedup, applicable UI/runtime candidates get live UI evidence first; the audited candidate set then goes to a **different-family model whose only job is to refute it**, which also returns a short sweep of what every lane missed.

Expect a structured report: roster, lane yield (what each lane returned versus what survived), live UI status when applicable, findings-audit status, verifier verdict counts (`confirmed/refuted/undecidable`), miss-sweep counts, kept/dropped findings with reasons, draft comments awaiting your go-ahead, and UI evidence attachments for UI feedback.

Use it when the change needs independent review plus adversarial refutation (cross-family preferred at equal capability, SOP §3.5). It scales from one sighted lane + verifier to extra lanes only when scope evidence warrants them.

## Reading any review's output

- Findings are ordered by severity; each carries evidence (file:line, command output) — no evidence, no finding.
- `Compatibility impact:` line tells you if behavior was removed/kept — it must say `none` unless you asked otherwise.
- "Post-review: clean" means the review's own fixes were audited too.

## Pivots from here

- Review found an architectural smell → hand it to `k-codebase-design` ("design a better seam for this").
- Review found a bug worth its own work → `draft an issue from finding 2`.
- A finding needs a live browser check → the agent does this itself in rungs 2–3; in rung 1 just ask `verify this in the browser`.
