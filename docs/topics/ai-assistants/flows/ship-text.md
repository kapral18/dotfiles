---
sidebar_position: 7
title: "Ship issues, PRs, and review replies"
---

# Ship issues, PRs, and review replies

Everything human-visible follows one iron rule ([the gate](../system-prompt/side-effect-gates.md)): **the agent drafts, you see the exact payload and target, nothing is sent until you approve.** These flows produce the text; the `github` skill performs the click, gated.

**Prerequisites:** a session; `gh` authenticated for the actual side effects.

## Draft an issue

```text
draft an issue: todo.py crashes with a TypeError traceback when the db file is the old string format
```

The draft comes back with Problem / Expected / Actual / numbered Reproduction — with your local paths, hostnames, and session junk **scrubbed into portable steps** (that sanitization is the skill's job, not yours). If the repro or environment detail is missing, it says so explicitly instead of inventing one.

Then: `file it` → the agent shows the final title/body/repo/labels once more and creates it only after your yes.

## Draft a PR body

```text
draft the PR text for this branch
```

The Test Plan section is the strict part: it contains **commands actually run with their observed results** — if manual verification didn't happen, the draft says so and gives reviewers the steps instead of pretending. `Closes #N` only appears when the issue is genuinely closed by the change.

## Reply to review threads

```text
address the review comments on PR #4321
```

Fixable comments get fixed in code; the rest get drafted replies, shown to you per-thread. Human-authored threads are **never** auto-replied — you approve each send. Only verified bot threads inside a flow you explicitly invoked can auto-resolve.

## Present a PR before review

```text
/present-pr
```

Builds a self-contained HTML walkthrough of the PR (what changed, in what order to read it, which files are load-bearing vs mechanical) that you can hand to reviewers. It verifies its own output renders (browser-checked, zero console errors) before showing you. Nothing is posted anywhere.

## Pivots from here

- Issue you're drafting turns out to already exist → the necessity check in [spec](spec-and-build.md) catches duplicates before writing; ask `has anyone filed this?` any time.
- PR body needs the change verified first → `verify this works end-to-end` before drafting, so the Test Plan writes itself from real runs.
