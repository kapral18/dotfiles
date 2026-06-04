# Shared Review Rules

All review modes load this file. Do not duplicate these rules in mode files.

## Read-Only Probes

- Start read-only investigation immediately. Do not ask for confirmation before read-only `git`/`gh` checks.

## Hard Constraints

- External truth applies: verify behavior under review (tests, repros, `/tmp` simulations) before asserting when practical.
- Code changes:
  - **Local changes mode** and **PR fix mode**: find issues and fix them in the working tree immediately. Code changes are expected as part of the workflow — no extra permission needed. Do not commit or push unless explicitly asked.
  - **PR review mode (self-review)**: same — find and fix in the working tree.
  - **PR review mode (reviewing others):** do not change code unless the user explicitly asks.
- Do not post to GitHub, submit reviews, apply labels, or resolve threads unless explicitly asked. Exception per the Human-Visible Publication Gate (SOP, `~/AGENTS.md`): a **verified bot-authored** thread may be auto-replied/auto-resolved inside an explicitly-invoked flow; any human-visible target stays supervised (draft -> show payload -> wait). Ambiguous/mixed threads fail safe to human.
- Assume the user started the agent inside the intended repo/worktree/session:
  - do not create/switch worktrees proactively
  - if the user explicitly asks to create/switch a worktree, use `~/.agents/skills/worktrees/SKILL.md`; for GitHub issue worktrees in agent contexts, prefer `,gh-worktree issue ... --branch ...`

## Base-Branch Context Gate (Mandatory)

Goal: compare the diff against how base (usually `main`) works today.

### Preflight (blocking, do first)

- You MUST run `list_indices` before selecting/using an index:
  - try both `scsi-main` and `scsi-local`
  - if both fail or neither exists, treat semantic search as unavailable
- If the user provided an index name:
  - verify it exists in the `list_indices` output
  - if it does not exist, stop and ask which index to use (default: the best evidence-based match for the current repo)
- If the user did not provide an index name:
  - use the single obvious repo-matching index from `list_indices`
  - if multiple equally plausible repo-matching indices remain, ask the user which one represents the base branch
  - if no repo-matching index exists, treat semantic search as unavailable and fall back to local sources
- Do not move on to base-context reasoning or comment drafting until this preflight is complete.

### If the repo is indexed

- Semantic code search is required for base-branch context.
  - Load and follow: `~/.agents/skills/semantic-code-search/SKILL.md`
  - You MUST invoke at least one SCSI tool (for example: `discover_directories`, `semantic_code_search`, `map_symbols_by_query`, `symbol_analysis`, or `read_file_from_chunks`) to establish base invariants.
- **SCSI reflects the latest main branch, not the current branch or PR.** All code returned by SCSI represents the base (pre-change) state. Use it strictly as comparison/background context to understand the codebase the changes are targeting. The PR/local diff is the ground truth for what is actually changing. When SCSI results conflict with the diff, the diff wins — the conflict is expected and simply means the PR modifies that code.
- Query strategy — generate questions from the diff:
  1. Read the diff to identify what changed.
  2. Generate semantic questions about the contracts, invariants, and patterns the changed code touches (e.g. "how is X validated elsewhere?", "what calls this function?", "what pattern does the codebase use for Y?").
  3. Query each question via SCSI tools against the repo index.
  4. Carry the answers as base-branch context into the review (for comparison and to understand surrounding code — not as current-branch truth).
- Use SCSI to learn base-branch implementation and invariants, then compare against the PR/local diff (ground truth).

### If the repo is not indexed / tools unavailable

- Use local sources instead:
  - `rg` + file reads
  - `git show <base>:<path>` for base-branch behavior
  - `git diff <base>...HEAD` for branch delta

### Base context reporting (required in every review output)

- Include exactly one line near the top of the output:
  - `Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<base>...HEAD`
  - `<reason>` MUST be one of:
    - `SCSI used`
    - `not indexed`
    - `tools unavailable`
    - `user-selected none`
- This line is reviewer metadata for the assistant's output. Do not include it in GitHub comment bodies.

## Truth Validation Framework

Use in every non-trivial review.

- Treat every claim as a hypothesis until verified.
- Establish base invariants first (SCSI when indexed; otherwise `git show <base>:<path>` + local `rg`).
- Validate PR/branch reality second (local diff + file reads).
- When evaluating a proposed change (review suggestion / reviewer request):
  - prefer the smallest reproduction in `/tmp` when possible
  - otherwise run the smallest safe experiment in the worktree
- If you changed code as part of an iteration cycle, re-run the repo's quality gates:
  - lint + type_check + tests (discover the correct commands from the repo; do not guess).
- Keep an evidence log per comment/thread: what base does, what changed, what you tested, and what you observed.

## State-Machine Verification Gate

Use for any reviewed behavior that is stateful, parser-like, branch-heavy, or dependent on ordered conditions: parsers, tokenizers, formatters, routing/matching logic, retry/workflow loops, permission matrices, compatibility-sensitive branching, or multi-flag control flow.

- Before saying the change is final, merge-ready, or a review concern is resolved, build or inspect a disposable harness under `/tmp/state-machine-verification/<pwd>/<topic>/<slug>/`.
- The harness must include a `manifest.json` with worktree path, topic, slug, target files/symbols, branch name, base/head refs when relevant, requested behavior, and compatibility intent.
- Model states, transitions, inputs, and terminal actions explicitly. Cover existing behavior buckets, requested behavior, boundary/malformed inputs, and regression-sensitive examples.
- Compare the implementation against an independent model/state table, not just itself. When behavior should be preserved, compare against base and classify each difference as intended or unexpected.
- In review-only PR mode for someone else's work, keep code read-only; use the harness to verify claims when safe, and surface missing or inadequate state-machine coverage as a test gap when risk remains.

## Deletion-Safety Audit (Run On Any Removal)

Trigger: the diff deletes files, exports, symbols, or behavior (`git diff --diff-filter=D --stat`, removed `export`s, deleted functions/branches). Before calling a deletion safe, verify each and report a one-line deletion ledger:

- **No live references:** `rg` the deleted symbol/file/path across the repo and public barrels/index files; confirm zero live importers/callers.
- **Public surface:** deleted exports are removed from barrels and are not part of a published package entry point still consumed downstream.
- **Behavior parity:** every behavior the deleted code provided is either intentionally dropped (user-approved per SOP `2.0`) or demonstrably replaced — name where each replaced behavior now lives.
- **Tests:** deleted tests were migrated, or removed only because the code they covered is gone; coverage for surviving behavior still exists.
- **Base comparison:** for branch-heavy/stateful deletions, compare against base behavior buckets (see State-Machine Verification Gate) and classify each difference as intended or unexpected.
- **Disclosure:** meaningful deleted infrastructure is reflected in the PR description (Summary/Fix), not silently dropped.

## Historical-Rationale Gate (Deleting/Replacing Long-Lived Infra)

Trigger: removing or replacing a custom/legacy stack, a helper that predates current infra, or anything called "obsolete"/"legacy"/"why does this exist". Understand the origin before the removal is final.

- **Trace origin:** `git log --follow --oneline -- <path>` and `git blame <base> -- <path>` (or `git log -L` for a function) to find the introducing commit(s).
- **Link intent:** open the offending PR(s)/issue(s) (`gh pr view`, `gh issue view`) to learn the original reason.
- **Classify:** was the behavior being removed (a) the original intended purpose, or (b) drift/side effect that later infra made obsolete?
- **Decide narrative:** if removal corrects historical drift, the PR `## Root Cause` must state the original reason and why it no longer applies. If it removes still-needed behavior, stop — that is not a safe deletion.

## Coverage Checklist (Do Not Skip)

- security issues
- logic/correctness/invariants
- data-loss risk
- performance regressions
- test gaps (especially risky changes without tests)
- documentation gaps
- maintainability/complexity
- true nits

## Severity Definitions (Internal Only; Do Not Prefix Comments With These)

- CRITICAL: security vulnerability, data loss/corruption, authz/authn bypass, crash, or unsafe migration.
- HIGH: user-visible bug, broken invariant, serious performance regression, or high operational risk.
- MEDIUM: maintainability risk, unclear behavior, missing tests for a risky change, or non-trivial tech debt.
- LOW: small improvements, clarity, naming/style consistency (true nits).

## Draft Style (Public-Ready)

- Tone, concision, and the "replying to someone's response" triage pattern are centralized in `~/.agents/skills/communication/SKILL.md` — follow it for all comment/reply/description wording. The rules below are review-specific additions only.
- No headline summaries or category prefixes (exception: `nit:` allowed only for true nits).
- Keep explanations simple; prefer tiny examples, pseudocode, or ASCII sketches.
- Avoid redundant "Ref:" links when the comment is already attached to the exact line.
- Do not mention anchoring/tooling limitations in the comment body ("can't anchor inline", "not in diff hunks").
- In review comment bodies, whenever you reference code (file path, function, symbol, line/range, snippet location), use a clickable source link to the exact location on the PR head SHA; do not leave plain unlinked code/file references.
- **Commit references must be clickable links, never bare hashes or inline code.** Use the full GitHub URL: `https://github.com/OWNER/REPO/commit/FULL_SHA` (or `/pull/NUM/commits/FULL_SHA` when referencing a PR commit). Resolve `OWNER/REPO` from the current repo and expand short hashes to full SHA before linking.
- Use `suggestion` blocks only when confident the replacement matches the exact anchored line(s).

## Pending Review Semantics (Definition + Content Boundary)

Terminology used in these skills:

- "pending review" means a GitHub PR review whose API `state` is `PENDING` (draft):
  - it is visible only to the reviewer who created it until they submit it (COMMENT/APPROVE/REQUEST_CHANGES)
  - it is _not_ visible to the PR author or other reviewers while pending
  - assume everything in it may become public once submitted; draft accordingly

Content boundary:

- A pending review must contain only public-ready review content: objective, presentable, and directly related to the code under review.
- Never include the agent's internal reasoning, excerpts of internal conversation, tool outputs, or meta-justifications. The PR author should not learn that internal discussion exists.
- Prefer concrete fixes:
  - best: GitHub `suggestion` blocks with exact replacement code
  - otherwise: small code snippets or precise, actionable steps (avoid vague descriptions).

## Review Verdict (PR Review Mode Only)

After all findings are drafted, recommend an overall verdict:

- **Approve**: no CRITICAL/HIGH findings remain; all findings are LOW/MEDIUM nits or suggestions.
- **Request changes**: at least one CRITICAL or HIGH finding that must be addressed before merge.
- **Comment only**: findings exist but are informational/advisory; merge is not blocked.

State the recommendation and the reason (e.g. "Verdict: request changes — the unchecked error on line 42 can cause silent data loss"). The user decides whether to actually submit the verdict.

## Review Persistence

The internal findings queue and review progress are ephemeral by default. Survive conversation pruning by reusing the existing hook-managed memory system — do not invent a parallel store:

- Convention: `/tmp/specs/<pwd>/` from the parent SOP. Topic key: `review-<pr-number>` for PR modes (else `review`).
- The agent-owned intent file is `<topic>.txt`. The hook system additionally maintains `<topic>.worklog.jsonl`, `<topic>.evidence_state.json`, and `<topic>.evidence_decisions.jsonl`. Inspect state with `,agent-memory status` (resolves the active topic and lists the files).
- On the first turn of a PR flow, check for the spec file and resume from it. After each thread/finding, append to `<topic>.txt` so the loop is resumable:
  - findings/threads: `comment_id`, author-type (`human`|`bot`), severity, file:line, one-line description, status (`open`|`fixed`|`dismissed`|`resolved`|`awaiting-approval`)
  - decision + evidence per thread (what base does, what changed, what was tested)
  - validation runs: commands + pass/fail + head SHA pushed
  - PR body obligations still open (sections to update, deletions to disclose)
  - open audit questions (e.g. unresolved `,kbn-pr-audit` findings)
  - current position in the queue (for iterative/Drain Mode) and base-context metadata
- On subsequent turns, check for the spec file first and resume from it if present.

## Posting Boundary

- Draft in chat first.
- If the user asks to post/submit/apply anything to GitHub:
  - keep the draft content from the review mode
  - then invoke the `github` skill via the Skill tool
  - get explicit approval for the GitHub side effect
- Human-Visible Publication Gate (SOP, `~/AGENTS.md`): the explicit-approval requirement above is absolute for any human-visible target. The only automation carve-out is a verified bot-authored thread (see `pr_fix.md` Drain Mode), which may be auto-replied/auto-resolved inside a flow the user already invoked.
