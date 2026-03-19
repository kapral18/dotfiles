---
name: review
description: |-
  Review local changes or PRs. Use when reviewing changes, continuing a
  review, addressing review threads, or rechecking PR-related changes.
---

# Review Router

Goal:

- route "review" requests to the smallest correct mode (natural discovery)
- keep shared review rules always loaded, while mode details are lazy-loaded

Contract:

- This router is the entrypoint. If another skill points you here for shared
  rules, you may skip routing and jump to the relevant section.
- After you select a mode, open exactly one primary mode file and follow it:
  - `~/.agents/skills/review/references/local_changes.md`
  - `~/.agents/skills/review/references/pr_start.md`
  - `~/.agents/skills/review/references/pr_iterative.md`
  - `~/.agents/skills/review/references/pr_reply.md`
  - `~/.agents/skills/review/references/pr_change_cycle.md`
- Load secondary skills only when this router or the selected mode requires them
  (for example: semantic code search for base context, or GitHub workflow when
  the user explicitly asks to post).
- Do not load `~/.agents/skills/github/SKILL.md` for read-only PR
  inspection/review. Only load it when the user explicitly asks to post/submit
  anything to GitHub.
- If the user wants review analysis and GitHub posting in the same request, the
  review router stays primary. Draft/verify through review mode first, then load
  `~/.agents/skills/github/SKILL.md` only for the posting step.

## PR Detection (Do First When PR Is Involved)

If the user mentions or strongly implies a PR (PR/pull request, PR review,
threads, "check my PR comment", "recheck this fix from the PR", etc.):

- First step is PR discovery via `,gh-prw` (read-only):
  - `,gh-prw --number`
  - If it fails once, stop and ask for the PR URL/number.

Continuity rule:

- If the conversation is already clearly in a specific mode, stay in that mode
  when the user says "continue" / "next" unless they explicitly switch targets.

## Mode Selection (Intent + Evidence)

Pick exactly one mode. If ambiguous, ask one fork-closing question and state a
default.

Mode: PR thread replies

- Use when: the user asks to reply to reviewer comments, address conversations,
  or resolve existing review threads.
- Then open: `~/.agents/skills/review/references/pr_reply.md`

Mode: PR change-cycle (apply fixes one thread/comment at a time)

- Use when: the user wants to address reviewer feedback by iterating on code
  changes with verification after each cycle ("apply the requested changes",
  "let's fix review comments", "one comment at a time until resolved").
- Then open: `~/.agents/skills/review/references/pr_change_cycle.md`

Mode: PR iterative (one new comment at a time)

- Use when: the user wants one new top-level review comment per turn for a PR
  ("what's the next comment", "continue the review", "one comment at a time").
- Then open: `~/.agents/skills/review/references/pr_iterative.md`

Mode: PR start (initial batch draft)

- Use when: the user wants an initial full PR review drafted in one go, or the
  user provides a PR URL/number and says "review" without asking for reply-only
  or one-at-a-time.
- Also use when: the user asks you to recheck/verify whether a PR fix resolves a
  bug ("does this PR fix it", "can you recheck", "verify this fix", "check my
  comment", "is it resolved on the updated branch").
- Then open: `~/.agents/skills/review/references/pr_start.md`

Mode: local changes review (working tree or branch delta)

- Use when: the user asks to review local changes/diff, or when there is no PR
  for the current branch and the user still wants a review.
- Then open: `~/.agents/skills/review/references/local_changes.md`

If the user's intent is still unclear, resolve via local context (do not guess):

- If not in a git repo:
  - Ask: "Is this a GitHub PR review (send URL/number), or a local repo changes
    review?"
- If in a git repo:
  - Run `git status --porcelain=v1 -b` (read-only, do not ask to proceed).
  - Independently check both:
    - whether staged/unstaged changes exist
    - whether `,gh-prw --number` resolves a PR for the current branch
  - If both are true, ask: "Should I review the local working tree diff, or the
    GitHub PR diff/threads?" Default: local working tree first.
  - If only local changes exist: local changes mode.
  - If only a PR exists: PR start mode.
  - If neither exists: local changes mode (branch delta).

Ambiguity rule:

- If both a PR exists and the working tree has local changes and the user just
  says "review", ask: "Should I review the local working tree diff, or the
  GitHub PR diff/threads?" Default: local working tree first.

## Shared Rules (All Modes)

Read-only probes:

- Start read-only investigation immediately. Do not ask for confirmation before
  read-only `git`/`gh` checks.

Hard constraints:

- External truth applies: verify behavior under review (tests, repros, `/tmp`
  simulations) before asserting when practical.
- Do not change code unless the user asked you to iterate on fixes.
  - If the user wants to apply reviewer suggestions / make PR changes, use PR
    change-cycle mode.
- Do not post to GitHub, submit reviews, apply labels, or resolve threads unless
  explicitly asked.
- Assume the user started the agent inside the intended repo/worktree/session:
  - do not create/switch worktrees proactively
  - if the user explicitly asks to create/switch a worktree, use
    `~/.agents/skills/worktrees/SKILL.md` and prefer `,w`

Base-branch context (mandatory):

- Goal: compare the diff against how base (usually `main`) works today.

Preflight (blocking, do first):

- You MUST run `list_indices` before selecting/using an index:
  - try both `scsi-main` and `scsi-local`
  - if both fail or neither exists, treat semantic search as unavailable
- If the user provided an index name:
  - verify it exists in the `list_indices` output
  - if it does not exist, stop and ask which index to use (default: the best
    evidence-based match for the current repo)
- If the user did not provide an index name:
  - use the single obvious repo-matching index from `list_indices`
  - if multiple equally plausible repo-matching indices remain, ask the user
    which one represents the base branch
  - if no repo-matching index exists, treat semantic search as unavailable and
    fall back to local sources
- Do not move on to base-context reasoning or comment drafting until this
  preflight is complete.

If the repo is indexed:

- Semantic code search is required for base-branch context.
  - Load and follow: `~/.agents/skills/semantic_code_search/SKILL.md`
  - You MUST invoke at least one SCSI tool (for example: `discover_directories`,
    `semantic_code_search`, `map_symbols_by_query`, `symbol_analysis`, or
    `read_file_from_chunks`) to establish base invariants.
- Query strategy — generate questions from the diff:
  1. Read the diff to identify what changed.
  2. Generate semantic questions about the contracts, invariants, and patterns
     the changed code touches (e.g. "how is X validated elsewhere?", "what calls
     this function?", "what pattern does the codebase use for Y?").
  3. Query each question via SCSI tools against the repo index.
  4. Carry the answers as working context into the review.
- Use SCSI to learn base-branch implementation and invariants, then compare
  against the PR/local diff (ground truth).

If the repo is not indexed / tools unavailable:

- Use local sources instead:
  - `rg` + file reads
  - `git show <base>:<path>` for base-branch behavior
  - `git diff <base>...HEAD` for branch delta

Base context reporting (required in every review output):

- Include exactly one line near the top of the output:
  - `Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<base>...HEAD`
  - `<reason>` MUST be one of:
    - `SCSI used`
    - `not indexed`
    - `tools unavailable`
    - `user-selected none`
- This line is reviewer metadata for the assistant's output. Do not include it
  in GitHub comment bodies.

Truth validation framework (use in every non-trivial review):

- Treat every claim as a hypothesis until verified.
- Establish base invariants first (SCSI when indexed; otherwise
  `git show <base>:<path>` + local `rg`).
- Validate PR/branch reality second (local diff + file reads).
- When evaluating a proposed change (review suggestion / reviewer request):
  - prefer the smallest reproduction in `/tmp` when possible
  - otherwise run the smallest safe experiment in the worktree
- If you changed code as part of an iteration cycle, re-run the repo's quality
  gates:
  - lint + type_check + tests (discover the correct commands from the repo; do
    not guess).
- Keep an evidence log per comment/thread: what base does, what changed, what
  you tested, and what you observed.

Coverage checklist (do not skip):

- security issues
- logic/correctness/invariants
- data-loss risk
- performance regressions
- test gaps (especially risky changes without tests)
- documentation gaps
- maintainability/complexity
- true nits

Severity definitions (internal only; do not prefix comments with these):

- CRITICAL: security vulnerability, data loss/corruption, authz/authn bypass,
  crash, or unsafe migration.
- HIGH: user-visible bug, broken invariant, serious performance regression, or
  high operational risk.
- MEDIUM: maintainability risk, unclear behavior, missing tests for a risky
  change, or non-trivial tech debt.
- LOW: small improvements, clarity, naming/style consistency (true nits).

Draft style (public-ready):

- Tone: direct, casual, friendly.
- No headline summaries or category prefixes (exception: `nit:` allowed only for
  true nits).
- Keep explanations simple; prefer tiny examples, pseudocode, or ASCII sketches.
- A collaborative close such as `Wdyt` is optional; use it only when it fits the
  comment naturally.
- Keep claims honest: observed (evidence) vs inferred (hypothesis) vs
  recommended (action).
- Do not mention internal tooling, agents, APIs, payloads, rate limits, or error
  codes.
- Do not talk about anchoring/tooling limitations ("can't anchor inline", "not
  in diff hunks").
- Do not include meta like "draft/pending review" in the comment body unless the
  user explicitly wants that.
- Avoid redundant "Ref:" links when the comment is already attached to the exact
  line.
- If you need to reference nearby lines, include a deep link to the exact source
  location (PR head SHA for PRs).
- Use `suggestion` blocks only when confident the replacement matches the exact
  anchored line(s).

Posting boundary:

- Draft in chat first.
- If the user asks to post/submit/apply anything to GitHub:
  - keep the draft content from the review mode
  - then switch to `~/.agents/skills/github/SKILL.md`
  - get explicit approval for the GitHub side effect
