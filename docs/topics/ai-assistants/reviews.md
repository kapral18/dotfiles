---
sidebar_position: 2
---

# Review Workflow

How an assistant reviews your changes or a PR. This is the `review` skill ([`home/exact_dot_agents/exact_skills/exact_review`](../../../home/exact_dot_agents/exact_skills/exact_review)) — the agent reviewing your diff. The inverse (you reviewing the agent's diff in a TUI) is [Reviewing agent diffs](reviewing-diffs.md).

Use when continuing a review, addressing review threads, or rechecking PR-related changes. The router (below) loads shared rules and PR-common setup once, then picks exactly one mode. The separate `/agent-review` skill wraps this methodology when you want the multi-agent topology.

## Multi-agent topology

`/agent-review` is the orchestration entrypoint. Cursor, Copilot, Claude, Codex, Gemini, and Amp bridge it through their native isolation mechanisms where available:

1. The controller resolves the route and scope packet: PR/local mode, role, target diff/PR/thread set, base branch, user constraints, and expected output.
2. Two read-only reviewer workers run in parallel when the harness supports it:
   - Cursor/Copilot use the GPT and Opus lanes.
   - Claude uses `reviewer` twice through `Task` with Claude model overrides.
   - Codex uses `spawn_agent` roles and runs two `review-worker` agents with distinct angles.
   - Gemini uses `review-gemini-pro` and `review-gemini-flash`.
   - Amp uses two generic `Task` subagents with the shared worker contract.
3. For other-authored or unknown-author PRs, `pr-necessity-auditor` checks whether the PR is sensible, correctly open, and still needed. It reconstructs author intent from the PR and references, searches related GitHub/Slack context when available, inspects git history, and looks for overlapping open or recently merged cross-cutting work.
4. `live-ui-review` first decides applicability from the changed paths and candidate findings. When UI/runtime behavior is in scope, it checks the configured targets with Playwriter and returns comparison evidence or a target/branch blocker.
5. `findings-auditor` audits the reviewer outputs before any action. It is an investigation agent: it flags redundancy, verbosity, semantic + logical duplication, and gaps in the candidate finding set.
6. The controller aggregates the investigation outputs, then judges what to fix or draft through mode-correct review rules. PR modes use PR dedup, PR artifact truth filtering, the PR necessity/correctly-open audit, and PR CI coverage gates; local changes are judged against the staged/unstaged/range scope without PR-thread or PR-CI exemptions. Only the controller acts.

Model names and subagent mechanisms are per-runtime. Cursor's `gpt-5.5-extra-high` / `claude-opus-4-8-xhigh` IDs are not Copilot IDs; Cursor review agents pin those models in frontmatter because omitted `model` inherits the parent/default model, which can be `composer-2.5-fast`. Copilot uses `gpt-5.5` / `claude-opus-4.8` plus `effortLevel: xhigh`. Codex and Amp do not have a Claude Opus lane in the verified local interface, so they preserve the two-worker isolation and distinct review angles rather than exact model parity. Gemini has native subagents but they cannot call other subagents, so the main Gemini session remains the controller.

The controller does not load or run the full review methodology before fan-out. Worker profiles are intentionally read-only and recursion-safe; they load the review skill for methodology in isolated contexts and return candidate findings. The controller only routes, fans out, aggregates, filters, and acts after the normal gates.

Its configured targets are `http://kibana-main.local:5602` for base and `http://kibana-feat.local:5601` for PR/head. It uses Playwriter target checks only when the applicability gate says UI/runtime behavior is in scope.

## Base-branch context and semantic search

Review skills require comparing your local diff/PR against how base (usually `main`) works today.

If semantic code search (SCSI) is available and the current repo is indexed, it is required for base-branch context:

- Preflight is blocking: run `list_indices` first (do not guess an index; try both `scsi-main` and `scsi-local` when both exist).
- If the user provided an index name, still run `list_indices` and verify the index exists before using it.
- If the user did not provide an index name, use the single obvious repo-matching index from `list_indices`; ask only when multiple equally plausible matches remain after evidence-based filtering.
- Use SCSI results as base-branch context only; validate the actual change via local git diffs and file reads.

Review outputs also include a single reviewer-metadata line so it's obvious what was used for base context:

```text
Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<scope>
```

`<scope>` is the actual diff under review, such as `<base>...HEAD`, `--cached`, `working-tree`, or `--cached + working-tree`.

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
  - `judging_core.md` — the surface-agnostic judging engine: truth validation, state-machine gate, deletion-safety, historical-rationale, coverage checklist, severity, and the post-review four-dimension lens + stage (loaded once by the router, before any mode)
  - `shared_rules.md` — the PR/SCSI/GitHub-delivery rules layered on top of the core: base-context gate, read-only probes, hard constraints, draft style, pending-review semantics, review verdict, review persistence, posting boundary (loaded once by the router)
  - `pr_common.md` — PR resolution, exhaustive GitHub Context Intake + Reference Resolution, Ambient Topic Exploration, PR Necessity + Correctly-Open Audit, media evidence, anchoring, deep links (loaded once for PR modes)
  - `local_changes.md` — local diff / branch delta review
  - `pr_review.md` — initial or continued PR review (batch or one-at-a-time)
  - `pr_fix.md` — address reviewer feedback (reply and/or code changes per thread)

The PR/issue intake gate is deliberately exhaustive: read complete PR and issue descriptions/bodies line-by-line; every conversation comment, review body, review comment, thread, and reply; every image/GIF/video or attachment (videos by significant frame/scene/state transition); and every recursively discovered PR/issue/comment/media/link until no reachable relevant reference remains unread. GitHub posting and PR/issue composition skills reuse the same gate when their output depends on existing PR/issue/comment context.

For disagreements or missing rationale, the review skill adds bounded **Ambient Topic Exploration**: build a topic map, search related GitHub issues/PRs, GitHub Discussions via GraphQL `SearchType.DISCUSSION`, and Slack MCP public/team channels when available, then read high-signal hits with the same intake rules. Skip it for routine reviews where direct context and base-branch context are enough.

For other-authored or unknown-author PRs, the review skill also runs a **PR Necessity + Correctly-Open Audit** before drafting. It classifies author intent, whether the PR is procedurally correctly open, whether the work is still needed, and whether similar cross-cutting work is already open or recently merged. Slack evidence is used only when Slack tools are available and private channels/DMs require explicit consent.

## Post-review stage (verifying the review's own fixes)

Every change-producing flow (local-changes verify-and-fix, PR-fix self-fixes, self-review, light-review) ends with a **post-review stage** that is distinct from verifying the original diff: it runs over the **fix diff** — the changes the review just made — and answers "are the review changes well done?".

The stage applies the canonical **four dimensions** (defined verbatim in `judging_core.md`, never renamed):

- **Redundancy** — the fix repeats something already present (re-implements a helper, re-states a rule, adds an already-present path).
- **Verbosity** — the fix is bloated beyond what the change needs (narration comments, ceremony, over-explanation).
- **Semantic + logical duplication** — two places now express the same meaning/behavior via different text (parallel branches that should be one; divergent-but-equivalent logic) — the subtle axis literal-clone detectors miss.
- **Gaps** — the fix is incomplete (own stranded dead code, an unupdated co-edit-set member like a doc/diagram/census, a half-applied rename, a referenced-but-missing file).

Where the flow can edit (own work / self-review), the stage resolves hygiene findings in the working tree and re-gates; in read-only contexts (reviewing others, read-only subagents) it surfaces them as findings. The on-demand `post-review` subagent (Claude and Pi) or `findings-auditor` agent (Cursor/Copilot `/agent-review`) runs only this lens over a named change set or candidate finding set.

## Light review (proportional depth)

[`light-review`](../../../home/exact_dot_agents/exact_skills/exact_light-review) is a separate skill for a fast, in-place audit of a low-risk, self-authored changeset. It shares the same `judging_core.md` engine (coverage checklist + four-dimension lens) but drops the mandatory SCSI/base-context preflight and GitHub machinery — base context is opt-in, and the post-review hygiene lens is foregrounded. It escalates to the full `review` skill for PRs, others' code, base-context-dependent correctness, or risky/stateful changes. The `change-auditor` subagent (Claude + Pi) is its read-only delegated form.

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

- **Human-Visible Publication Gate** (SOP `3.5` in the single source [`home/readonly_AGENTS.md`](../../../home/readonly_AGENTS.md); `~/CLAUDE.md` and `~/.gemini/GEMINI.md` are symlinks to it; referenced by `github`, `review/shared_rules.md`, `review/pr_fix.md`): anything a human will see (PR/issue replies, review submissions, resolving a human thread) is always drafted and supervised before sending. Verified bot-authored threads (`user.type == "Bot"`, `[bot]` login, or known-bot allowlist) may be auto-replied/auto-resolved inside an explicitly-invoked flow. Ambiguous or mixed human+bot threads fail safe to human.
- **PR-fix Drain Mode**: when the user explicitly asks to batch ("repeat the process", "you know the drill", "address all"), `pr_fix.md` drains threads back-to-back — auto-finishing bot threads and queuing human-thread drafts for approval — instead of re-asking after every single thread.
- **Deletion-Safety Audit** (`review/judging_core.md`): any removal (files/exports/symbols/behavior) must verify no live references, public-surface cleanup, behavior parity in the replacement, test migration, base comparison, and PR-body disclosure.
- **Historical-Rationale Gate** (`review/judging_core.md` + `compose-pr`): removing/replacing long-lived or "legacy" infra requires tracing the origin (`git log --follow`, blame, linked PR/issue) and, when correcting historical drift, stating the original reason in the PR `## Root Cause`.
- **Readiness audit CLI**: [`,kbn-pr-audit`](../../../home/exact_bin/executable_,kbn-pr-audit) is a read-only check (see [Custom commands](../workflow/custom-commands.md)) that surfaces the above drift before a reply/resolve/push cycle; it never mutates GitHub.

## Related

- [The Agentic Operating System](index.md) — governance layer and skills
- [Reviewing agent diffs](reviewing-diffs.md) — the inverse loop (`tuicr`)
- [Ralph orchestrator](ralph.md) — reviewer/re-reviewer roles invoke this skill on elastic repos
