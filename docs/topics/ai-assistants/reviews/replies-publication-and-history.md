---
sidebar_position: 4
title: Replies, publication, and history
---

# Replies, publication, and history

Review text is human-visible output, so the workflow separates drafting from posting. This page collects the reply style, router behavior, and safety gates that apply before comments, resolves, deletes, or history-sensitive changes reach GitHub.

## Mental model

| Concern          | Rule                                                                                         |
| ---------------- | -------------------------------------------------------------------------------------------- |
| Reply style      | draft direct, anchored review feedback without noisy quoting                                 |
| Router behavior  | choose exactly one review mode before loading shared rules                                   |
| Publication      | draft and supervise anything a human will see                                                |
| Bot carve-out    | auto-reply/auto-resolve only verified bot-authored threads inside an explicitly-invoked flow |
| Deletion/history | verify removals and trace rationale for long-lived or legacy infra                           |

## Using it

### Reply style

When drafting PR thread replies:

- Do not use `RE:`.
- Default: reply directly; do not quote when the whole parent comment is the reference.
- If you need to point at a specific fragment, use a minimal blockquote (`> ...`) and then reply.
- A closing prompt like `Wdyt` is optional, not mandatory. Use it only when it fits the tone of the specific comment.
- Default to inline anchored comments for code-review feedback, not PR-level summary bodies, unless explicitly requested.
- Any code/file/symbol reference in a comment body must be a clickable source link to the exact location on the PR head SHA.
- UI-related comments, replies, or PR-level feedback drafted after `/k-agent-review` or `live-ui-review` need screenshot handoff evidence kept outside the body, or a valid blocker/non-applicability reason.
- Local screenshot paths never go into GitHub bodies. After explicit approval, `k-github` may upload them through an editor in the destination repository and embed the resulting `user-attachments` URLs; the upload preserves any existing draft text and inherits that repository's visibility. Before upload, each file is viewed, md5s are checked for unintended duplicates, and image dimensions are checked for sane legibility.

### Router behavior

The review router selects exactly one of four modes:

| Mode          | Meaning                                               |
| ------------- | ----------------------------------------------------- |
| local changes | review the local diff / branch-delta                  |
| PR review     | review an initial or continued PR                     |
| PR fix        | address feedback                                      |
| plan review   | judge a design/plan document against codebase reality |

Shared rules and PR-common setup are loaded once by the router, not duplicated per mode.

When both a dirty working tree and a current-branch PR exist, the router asks which target to review instead of silently forcing local review first.

GitHub posting stays outside read-only review mode until the user explicitly asks for a side effect.

## Reference: publication, deletion, and history gates

| Gate                               | Source                                                                                                                                                                                                                                                        | Rule                                                                                                                                                                                                                  |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Human-Visible Publication Gate     | SOP `3.6` in the single source [`home/readonly_AGENTS.md`](../../../../home/readonly_AGENTS.md); `~/CLAUDE.md` and `~/.gemini/GEMINI.md` are symlinks to it; referenced by `k-github`, `k-review/references/shared_rules.md`, `k-review/references/pr_fix.md` | anything a human will see — PR/issue replies, review submissions, resolving a human thread — is always drafted and supervised before sending                                                                          |
| Bot-authored thread carve-out      | same gate                                                                                                                                                                                                                                                     | verified bot-authored threads may be auto-replied/auto-resolved inside an explicitly-invoked flow                                                                                                                     |
| Pending review merge guard         | GitHub side-effect layer                                                                                                                                                                                                                                      | reads any current-account `PENDING` review and refuses to create/submit fragmented feedback unless the review draft includes a reconciliation ledger                                                                  |
| PR-fix Drain Mode                  | `k-review/references/pr_fix.md`                                                                                                                                                                                                                               | when the user explicitly asks to batch (`repeat the process`, `you know the drill`, `address all`), drains threads back-to-back instead of re-asking after every single thread                                        |
| Deletion-Safety Audit              | `k-review/references/judging_core.md`                                                                                                                                                                                                                         | any removal of files/exports/symbols/behavior must verify no live references, public-surface cleanup, behavior parity in the replacement, test migration, base comparison, and PR-body disclosure                     |
| Historical-Rationale Gate          | `k-review/references/judging_core.md` + `k-compose-pr`                                                                                                                                                                                                        | removing/replacing long-lived or `legacy` infra requires tracing the origin (`git log --follow`, blame, linked PR/issue) and, when correcting historical drift, stating the original reason in the PR `## Root Cause` |
| Elastic/Kibana readiness audit CLI | [`,kbn-pr-audit`](../../../../home/exact_bin/executable_,kbn-pr-audit)                                                                                                                                                                                        | read-only Elastic/Kibana tool-pack check that surfaces PR-body/label/thread drift before a reply/resolve/push cycle; it never mutates GitHub                                                                          |

Verified bot-authored means `user.type == "Bot"`, a `[bot]` login, or a known-bot allowlist from the active domain overlay. Ambiguous or mixed human+bot threads fail safe to human.

In PR-fix Drain Mode, bot threads can be auto-finished and human-thread drafts are queued for approval.

See [Custom commands](../../workflow/custom-commands/index.md) for the `,kbn-pr-audit` command.
