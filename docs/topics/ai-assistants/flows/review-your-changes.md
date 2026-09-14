---
sidebar_position: 3
title: "Get your changes reviewed"
---

# Get your changes reviewed

Three review scopes share one final Verify stage. Select the scope from the change's risk before review; do not run each rung in sequence.

**Prerequisites:** a session in the repo with the changes (uncommitted, staged, a branch, or a PR number).

## Rung 1 — `/k-light-review`: your own low-risk changes

```text
/k-light-review
```

The root dispatches one isolated `change-auditor` worker for the final judgment against applicable correctness and hygiene criteria, consuming existing check evidence. Missing planned checks stay root-owned and run once in final Verify. On your own uncommitted changes, the root fixes findings inside the diff's own behavior in Produce before that final judgment — write scope, not review, is the authority, and the leaf worker stays read-only; scope-expanding findings come back as proposals. Findings do not authorize self-audits or convergence. Output names findings, applied fixes, evidence, and remaining gaps.

It will refuse and point up a rung when the target is a PR, someone else's code, or risky/stateful territory — that's the built-in escalation, not an error.

## Rung 2 — full `k-review`: PRs, others' code, risky changes

```text
review PR #4321
```

or for local work that needs base-branch context: `review my branch against main`.

Standard review dispatches one isolated `reviewer-worker` leaf for the substantive judgment in every mode. The root reads the complete primary PR discussion and references needed for named material questions, packs that context once, and the leaf traces base behavior and affected consumers from it. Until that leaf returns, the root reads only scope-level evidence (status, `--stat`, changed names, log, check receipts, discussion) and never diff hunks or changed-file bodies; worker-depth reads travel in the packet. Stateful risks need transition evidence from focused root-run tests or a disposable harness. Write scope, not authorship, grants edit authority: the root fixes your own branch in Produce before the final judgment while the leaf stays read-only; someone else's PR gets proposals until you say fix it. Known fixes belong to Produce before final Verify; publication retains exact-payload approval.

## Rung 3 — `/k-deep-review`: independent lanes + adversarial verification

```text
/k-deep-review PR #4321
```

Deep review dispatches distinct strong artifact-review and adversarial leaf packets as distinct questions against the same frozen candidate and shared evidence. It prefers a different model family at equal capability. Additional specialist lenses need independent risks; blind fresh-eyes applies only to comprehension risk and receives no narrative, history, or prior findings. Applicable live UI evidence belongs to this same final stage; the root selects it and views the returned artifacts.

Expect anchored findings, unresolved evidence gaps, relevant UI artifacts, and any requested publication draft. There is no findings-auditor, verifier-of-verifier, post-review, or automatic repair chain.

Use it when the change needs independent review plus adversarial challenge (SOP §3.7). Workers are leaves; the root owns scope, checks, and the terminal outcome.

## Reading any review's output

- Findings are ordered by severity; each carries evidence (file:line, command output) — no evidence, no finding.
- `Compatibility impact:` line tells you if behavior was removed/kept — it must say `none` unless you asked otherwise.
- Review alone does not authorize repairs; write scope does — your own changes are fixed in place, others' come back as proposals. In any task with existing authority, the root follows SOP §3.5 for scoped recovery and revalidation; a failed check does not require the same permission again.

## Pivots from here

- Review found an architectural smell → hand it to `k-codebase-design` ("design a better seam for this").
- Review found a bug worth its own work → `draft an issue from finding 2`.
- A finding needs a live browser check → the agent does this itself in rungs 2–3; in rung 1 just ask `verify this in the browser`.
