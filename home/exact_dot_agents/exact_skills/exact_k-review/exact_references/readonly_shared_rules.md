# Shared Review Rules

All review modes load this file. Do not duplicate these rules in mode files.

The surface-agnostic judging engine lives in `~/.agents/skills/k-review/references/judging_core.md`.

It covers:

- Truth Validation
- State-Machine Gate
- Deletion-Safety
- Replacement/Migration Parity
- Historical-Rationale
- Product-Flow Lens
- Signal-Quality Gate
- Systemic-Risk Checks
- Coverage Checklist
- Severity
- Post-Review Lens + Stage

Load it alongside this file.

This file carries only the PR/SCSI/GitHub-delivery rules layered on top of that core.

## Read-Only Probes

- Start read-only investigation immediately. Do not ask for confirmation before read-only `git`/`gh` checks.
- In large repositories, make first-pass git probes bounded: use `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false` for status, diff names, upstream, and log probes.
  If a plain git probe produces no output after one short wait, stop it and rerun the bounded form.
- Keep searches narrow by default: include path scopes, file globs, or exact symbols.
  When the harness provides native search/listing tools, prefer those for first-pass broad searches.
  Use shell `rg` only after narrowing by path, glob, or exact symbol; never run bare repo-root `rg <pattern>` in a large repository.
  Do not run broad repo-wide searches or dump full command output when a file list, count, or targeted lines answer the question.
- When command output is saved/truncated, recover only the exact lines needed for the current decision unless the decision depends on every item.

## Hard Constraints

- External truth applies: verify behavior under review (tests, repros, `/tmp` simulations) before asserting when practical.
- Code changes:
  - **Read-only delegated workers**:
    - never edit or run side effects
    - may run non-mutating verification at whatever depth is needed; use `/tmp` or isolated copies for disposable artifacts and do not write repo-local caches, start shared services, seed data, or mutate shared runtime state
    - do not skip useful full suites, deep searches, or heavyweight analysis only because they are expensive or another lane may also run them
    - if verification requires mutation or a shared/exclusive runtime, return the exact `verification_needed` to the parent/controller for serial handling
    - return proposed fixes to the parent controller
  - **Local changes mode with `authorship: self`** and **PR fix mode when edits are permitted**:
    - find issues and fix them in the working tree immediately
    - code changes are expected as part of the workflow
    - no extra permission needed
    - do not commit or push unless explicitly asked
  - **Local changes mode with `authorship: other` or `unknown`**: draft-only unless the user explicitly asks to fix/take over.
  - **PR review mode (self-review)**: same — find and fix in the working tree.
  - **PR review mode (reviewing others or unknown authorship):** do not change code unless the user explicitly asks to fix/take over and the flow switches to PR fix mode.
- Do not post to GitHub, submit reviews, apply labels, or resolve threads unless explicitly asked.
- Exception per the Human-Visible Publication Gate (SOP, `~/AGENTS.md`):
  - a **verified bot-authored** thread may be auto-replied/auto-resolved inside an explicitly-invoked flow
  - any human-visible target stays supervised: draft -> show payload -> wait
  - ambiguous/mixed threads fail safe to human
- Assume the user started the agent inside the intended repo/worktree/session:
  - do not create/switch worktrees proactively
  - if the user explicitly asks to create/switch a worktree:
    - use `~/.agents/skills/k-worktrees/SKILL.md`
    - for GitHub issue worktrees in agent contexts, prefer `,gh-worktree issue ... --branch ...`

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
  - Load and follow: `~/.agents/skills/k-semantic-code-search/SKILL.md`
  - You MUST invoke at least one SCSI tool to establish base invariants.
  - Example SCSI tools:
    - `discover_directories`
    - `semantic_code_search`
    - `map_symbols_by_query`
    - `symbol_analysis`
    - `read_file_from_chunks`
- **SCSI reflects the latest main branch, not the current branch or PR.**
  - All code returned by SCSI represents the base (pre-change) state.
  - Use SCSI strictly as comparison/background context.
  - Use it to understand the codebase the changes are targeting.
  - The PR/local diff is the ground truth for what is actually changing.
  - When SCSI results conflict with the diff, the diff wins.
  - That conflict is expected; it simply means the PR modifies that code.
- Query strategy — generate questions from the diff:
  1. Read the diff to identify what changed.
  2. Generate semantic questions about the contracts, invariants, and patterns the changed code touches.
     - "how is X validated elsewhere?"
     - "what calls this function?"
     - "what pattern does the codebase use for Y?"
  3. Query each question via SCSI tools against the repo index.
  4. Carry the answers as base-branch context into the review (for comparison and to understand surrounding code —
     not as current-branch truth).
- Use SCSI to learn base-branch implementation and invariants, then compare against the PR/local diff (ground truth).

### If the repo is not indexed / tools unavailable

- Use local sources instead:
  - `rg` + file reads
  - `git show <base>:<path>` for base-branch behavior
  - `git diff <base>...HEAD` for branch delta

### Base context reporting (required in every review output)

- Include exactly one line near the top of the output:
  - `Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<scope>`
  - `<reason>` MUST be one of:
    - `SCSI used`
    - `not indexed`
    - `tools unavailable`
    - `user-selected none`
  - `<scope>` MUST name the actual diff under review, for example:
    - `<base>...HEAD`
    - `<ref>...HEAD`
    - `--cached`
    - `working-tree`
    - `--cached + working-tree`
    - the explicit diff command from the scope packet
- This line is reviewer metadata for the assistant's output. Do not include it in GitHub comment bodies.

## Draft Style (Public-Ready)

- Tone, concision, and response triage are centralized in `~/.agents/skills/k-communication/SKILL.md`.
- Follow it for all:
  - comment wording
  - reply wording
  - description wording
- The rules below are review-specific additions only.
- No headline summaries or category prefixes (exception: `nit:` allowed only for true nits).
- Keep explanations simple; prefer tiny examples, pseudocode, or ASCII sketches.
- Avoid redundant "Ref:" links when the comment is already attached to the exact line.
- Do not mention anchoring/tooling limitations in the comment body ("can't anchor inline", "not in diff hunks").
- For UI-related comments, replies, or PR-level feedback drafted after `/k-agent-review` or `live-ui-review`, keep the screenshot handoff outside the body as UI evidence attachments, including folder-open/provided status.
  If screenshot evidence is missing without a valid blocker or non-applicability result, block/rerun instead of drafting text-only UI feedback.
  Never put local screenshot paths in GitHub comment, reply, review, or PR-level bodies.
- In review comment bodies, whenever you reference code, use a clickable source link to the exact location on the PR head SHA.
- Code references include:
  - file path
  - function
  - symbol
  - line/range
  - snippet location
- Do not leave plain unlinked code/file references.
- **Commit references must be clickable links, never bare hashes or inline code.**
- Use the full GitHub URL:
  - `https://github.com/OWNER/REPO/commit/FULL_SHA`
  - or `/pull/NUM/commits/FULL_SHA` when referencing a PR commit
- Resolve `OWNER/REPO` from the current repo.
- Expand short hashes to full SHA before linking.
- Use `suggestion` blocks only when confident the replacement matches the exact anchored line(s).

## Pending Review Semantics (Definition + Content Boundary)

Terminology used in these skills:

- "pending review" means a GitHub PR review whose API `state` is `PENDING` (draft):
  - it is visible only to the reviewer who created it until they submit it (COMMENT/APPROVE/REQUEST_CHANGES)
  - it is _not_ visible to the PR author or other reviewers while pending
  - assume everything in it may become public once submitted; draft accordingly

Content boundary:

- A pending review must contain only public-ready review content: objective, presentable, and directly related to the code under review.
- Never include:
  - agent internal reasoning
  - excerpts of internal conversation
  - tool outputs
  - meta-justifications
- The PR author should not learn that internal discussion exists.
- Prefer concrete fixes:
  - best: GitHub `suggestion` blocks with exact replacement code
  - otherwise: small code snippets or precise, actionable steps (avoid vague descriptions).

## Existing Pending Review Awareness (Before Drafting or Posting)

Before preparing a PR review draft, posting a pending review, or submitting an existing pending review, inspect review content already authored by the current authenticated account for the same PR.

This includes:

- any API `state: PENDING` review and its draft inline comments
- already-submitted review bodies, inline comments, thread replies, and PR-level comments authored by the same user/bot account
- review/comment/reply content created by previous agent sessions

Use GitHub's PR review APIs as the source of truth:

1. Resolve the current login: `gh api user --jq '.login'`.
2. List PR reviews: `gh api --paginate repos/OWNER/REPO/pulls/NUM/reviews`.
3. Select reviews with `state == "PENDING"` and `user.login == <current login>`.
4. For each selected review, read its draft comments with `gh api --paginate repos/OWNER/REPO/pulls/NUM/reviews/REVIEW_ID/comments`.
5. Re-read already-submitted comments/replies from the normal PR context intake and mark which were authored by the current login.

Reconcile new candidate findings against this ledger before producing the final draft:

- `covered_by_pending`: the existing pending review already states the same valid finding; do not draft a second copy.
- `merge_with_pending`: the same finding remains valid but the new run has better evidence, a better anchor, or a smaller fix;
  produce one merged replacement comment/body.
- `keep_existing_pending`: the existing pending finding is still valid and independent of the new findings; carry it forward once.
- `drop_stale_pending`: the existing pending finding is obsolete, incorrect on the current head, already fixed, or covered by public PR context; do not submit it.
- `conflict`: the existing pending review and new evidence disagree; resolve from current PR head evidence before posting.
  If unresolved, stop and surface the conflict rather than posting both.

If a pending review already exists and a merged payload is needed, do not create a second competing review.
Prepare one consolidated pending-review payload and let the GitHub side-effect layer delete/recreate the old pending review only after explicit approval.

Every PR-review output that may become GitHub review feedback must include a `Pending review reconciliation:` line with one of:
`none found`, `reused existing`, `merged replacement needed`, `stale pending dropped`, `blocked: <reason>`.

## Review Verdict (PR Review Mode Only)

After all findings are drafted, recommend an overall verdict:

- **Approve**: no CRITICAL/HIGH findings remain; all findings are LOW/MEDIUM nits or suggestions.
- **Request changes**: at least one CRITICAL or HIGH finding that must be addressed before merge.
- **Comment only**: findings exist but are informational/advisory; merge is not blocked.

State the recommendation and the reason.

Example:

- `Verdict: request changes — the unchecked error on line 42 can cause silent data loss`

The user decides whether to actually submit the verdict.

## Review Persistence

The internal findings queue and review progress are ephemeral by default.

Survive conversation pruning by reusing the existing hook-managed memory system.

Do not invent a parallel store:

- Convention: `/tmp/specs/<pwd>/` from the parent SOP. Topic key: `review-<pr-number>` for PR modes (else `k-review`).
- The agent-owned intent file is `<topic>.txt`.
- The hook system additionally maintains `<topic>.worklog.jsonl`.
- Never inspect review state with sessionless `,agent-memory status`; parallel sessions can resolve a different topic.
- If Agent Hook Context names the active topic, inspect that exact bucket with `,agent-memory status --topic <active-topic>`.
- If Topic Buckets supplies a session ID, bind the review bucket with `,agent-memory select <topic> --session-id <id> [--create]`, then inspect it with `,agent-memory status --session-id <id>`.
- On the first turn of a PR flow, check for the spec file and resume from it.
  After each thread/finding, append to `<topic>.txt` so the loop is resumable:
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
  - then invoke the `k-github` skill via the Skill tool
  - get explicit approval for the GitHub side effect
- Human-Visible Publication Gate (SOP, `~/AGENTS.md`):
  - explicit approval is absolute for any human-visible target
  - the only automation carve-out is a verified bot-authored thread
  - see `pr_fix.md` Drain Mode
  - bot-authored threads may be auto-replied/auto-resolved only inside a flow the user already invoked
