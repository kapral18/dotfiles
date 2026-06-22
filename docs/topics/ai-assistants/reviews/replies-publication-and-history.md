---
sidebar_position: 4
title: Replies, publication, and history
---

# Replies, publication, and history

## Reply style

When drafting PR thread replies:

- Do not use `RE:`.
- Default: reply directly; do not quote when the whole parent comment is the reference.
- If you need to point at a specific fragment, use a minimal blockquote (`> ...`) and then reply.
- A closing prompt like `Wdyt` is optional, not mandatory. Use it only when it fits the tone of the specific comment.
- Default to inline anchored comments for code-review feedback (not PR-level summary bodies) unless explicitly requested.
- Any code/file/symbol reference in a comment body must be a clickable source link to the exact location on the PR head SHA.

## Router behavior

- The review router selects exactly one of three modes: local changes, PR review, or PR fix (address feedback). Shared rules and PR-common setup are loaded once by the router, not duplicated per mode.
- When both a dirty working tree and a current-branch PR exist, the router asks which target to review instead of silently forcing local review first.
- GitHub posting stays outside read-only review mode until the user explicitly asks for a side effect.

## Publication gate, deletions, history

- **Human-Visible Publication Gate** (SOP `3.5` in the single source [`home/readonly_AGENTS.md`](../../../../home/readonly_AGENTS.md); `~/CLAUDE.md` and `~/.gemini/GEMINI.md` are symlinks to it; referenced by `github`, `review/shared_rules.md`, `review/pr_fix.md`): anything a human will see (PR/issue replies, review submissions, resolving a human thread) is always drafted and supervised before sending. Verified bot-authored threads (`user.type == "Bot"`, `[bot]` login, or a known-bot allowlist from the active domain overlay) may be auto-replied/auto-resolved inside an explicitly-invoked flow. Ambiguous or mixed human+bot threads fail safe to human. Pending review creation/submission also has a merge guard: the GitHub side-effect layer reads any current-account `PENDING` review and refuses to create/submit fragmented feedback unless the review draft includes a reconciliation ledger.
- **PR-fix Drain Mode**: when the user explicitly asks to batch ("repeat the process", "you know the drill", "address all"), `pr_fix.md` drains threads back-to-back — auto-finishing bot threads and queuing human-thread drafts for approval — instead of re-asking after every single thread.
- **Deletion-Safety Audit** (`review/judging_core.md`): any removal (files/exports/symbols/behavior) must verify no live references, public-surface cleanup, behavior parity in the replacement, test migration, base comparison, and PR-body disclosure.
- **Historical-Rationale Gate** (`review/judging_core.md` + `compose-pr`): removing/replacing long-lived or "legacy" infra requires tracing the origin (`git log --follow`, blame, linked PR/issue) and, when correcting historical drift, stating the original reason in the PR `## Root Cause`.
- **Elastic/Kibana readiness audit CLI**: [`,kbn-pr-audit`](../../../../home/exact_bin/executable_,kbn-pr-audit) is a read-only Elastic/Kibana tool-pack check (see [Custom commands](../../workflow/custom-commands/index.md)) that surfaces PR-body/label/thread drift before a reply/resolve/push cycle; it never mutates GitHub.
