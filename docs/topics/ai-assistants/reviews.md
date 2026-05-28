---
sidebar_position: 2
---

# Review Workflow

How an assistant reviews your changes or a PR. This is the `review` skill ([`home/exact_dot_agents/exact_skills/exact_review`](../../../home/exact_dot_agents/exact_skills/exact_review)) — the agent reviewing your diff. The inverse (you reviewing the agent's diff in a TUI) is [Reviewing agent diffs](reviewing-diffs.md).

Use when continuing a review, addressing review threads, or rechecking PR-related changes. The router (below) loads shared rules and PR-common setup once, then picks exactly one mode.

## Base-branch context and semantic search

Review skills require comparing your local diff/PR against how base (usually `main`) works today.

If semantic code search (SCSI) is available and the current repo is indexed, it is required for base-branch context:

- Preflight is blocking: run `list_indices` first (do not guess an index; try both `scsi-main` and `scsi-local` when both exist).
- If the user provided an index name, still run `list_indices` and verify the index exists before using it.
- If the user did not provide an index name, use the single obvious repo-matching index from `list_indices`; ask only when multiple equally plausible matches remain after evidence-based filtering.
- Use SCSI results as base-branch context only; validate the actual change via local git diffs and file reads.

Review outputs also include a single reviewer-metadata line so it's obvious what was used for base context:

```text
Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<base>...HEAD
```

Do not paste that line into GitHub comment bodies.

## Truth validation loop

For non-trivial review decisions (accepting a suggestion, pushing back, or proposing an alternative), use a strict verify-first loop:

- Base truth: establish what base branch does today (SCSI when indexed; otherwise `git show <base>:<path>` + local search).
- Change truth: validate what your branch/PR actually does (local diff + file reads).
- Assumption tests: reproduce in `/tmp` when possible; otherwise run the smallest safe experiment in the worktree.
- State-machine checks: for reviewed behavior that is stateful, parser-like, branch-heavy, or ordered-condition dependent, build or inspect a `/tmp/state-machine-verification/<pwd>/<topic>/<slug>/` harness before calling the change final, merge-ready, or a review concern resolved.
- Quality gates: if you changed code as part of an iteration cycle, re-run the repo's lint/type_check/tests trio (discover the correct commands from the repo; do not guess).

Skill support:

- Review modes live under `~/.agents/skills/review/references/`:
  - `shared_rules.md` — base-context gate, truth validation, state-machine verification gate, coverage checklist, severity, draft style, posting boundary (loaded once by the router)
  - `pr_common.md` — PR resolution, media evidence, anchoring, deep links (loaded once for PR modes)
  - `local_changes.md` — local diff / branch delta review
  - `pr_review.md` — initial or continued PR review (batch or one-at-a-time)
  - `pr_fix.md` — address reviewer feedback (reply and/or code changes per thread)

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

- **Human-Visible Publication Gate** (primary in [`home/readonly_AGENTS.md`](../../../home/readonly_AGENTS.md) — the SOP entrypoint Cursor/OpenCode load directly — and mirrored as SOP `3.5` in [`home/readonly_CLAUDE.md`](../../../home/readonly_CLAUDE.md) / [`home/dot_gemini/readonly_GEMINI.md`](../../../home/dot_gemini/readonly_GEMINI.md); referenced by `github`, `review/shared_rules.md`, `review/pr_fix.md`): anything a human will see (PR/issue replies, review submissions, resolving a human thread) is always drafted and supervised before sending. Verified bot-authored threads (`user.type == "Bot"`, `[bot]` login, or known-bot allowlist) may be auto-replied/auto-resolved inside an explicitly-invoked flow. Ambiguous or mixed human+bot threads fail safe to human.
- **PR-fix Drain Mode**: when the user explicitly asks to batch ("repeat the process", "you know the drill", "address all"), `pr_fix.md` drains threads back-to-back — auto-finishing bot threads and queuing human-thread drafts for approval — instead of re-asking after every single thread.
- **Deletion-Safety Audit** (`review/shared_rules.md`): any removal (files/exports/symbols/behavior) must verify no live references, public-surface cleanup, behavior parity in the replacement, test migration, base comparison, and PR-body disclosure.
- **Historical-Rationale Gate** (`review/shared_rules.md` + `compose-pr`): removing/replacing long-lived or "legacy" infra requires tracing the origin (`git log --follow`, blame, linked PR/issue) and, when correcting historical drift, stating the original reason in the PR `## Root Cause`.
- **Readiness audit CLI**: [`,kbn-pr-audit`](../../../home/exact_bin/executable_,kbn-pr-audit) is a read-only check (see [Custom commands](../workflow/custom-commands.md)) that surfaces the above drift before a reply/resolve/push cycle; it never mutates GitHub.

## Related

- [The Agentic Operating System](index.md) — governance layer and skills
- [Reviewing agent diffs](reviewing-diffs.md) — the inverse loop (`tuicr`)
- [Ralph orchestrator](ralph.md) — reviewer/re-reviewer roles invoke this skill on elastic repos
