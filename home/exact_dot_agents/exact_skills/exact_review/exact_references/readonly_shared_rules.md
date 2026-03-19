# Shared Review Rules

All review modes load this file. Do not duplicate these rules in mode files.

## Read-Only Probes

- Start read-only investigation immediately. Do not ask for confirmation before
  read-only `git`/`gh` checks.

## Hard Constraints

- External truth applies: verify behavior under review (tests, repros, `/tmp`
  simulations) before asserting when practical.
- Do not change code unless the user asked you to iterate on fixes.
- Do not post to GitHub, submit reviews, apply labels, or resolve threads unless
  explicitly asked.
- Assume the user started the agent inside the intended repo/worktree/session:
  - do not create/switch worktrees proactively
  - if the user explicitly asks to create/switch a worktree, use
    `~/.agents/skills/worktrees/SKILL.md` and prefer `,w`

## Base-Branch Context Gate (Mandatory)

Goal: compare the diff against how base (usually `main`) works today.

### Preflight (blocking, do first)

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

### If the repo is indexed

- Semantic code search is required for base-branch context.
  - Load and follow: `~/.agents/skills/semantic-code-search/SKILL.md`
  - You MUST invoke at least one SCSI tool (for example: `discover_directories`,
    `semantic_code_search`, `map_symbols_by_query`, `symbol_analysis`, or
    `read_file_from_chunks`) to establish base invariants.
- **SCSI reflects the latest main branch, not the current branch or PR.**
  All code returned by SCSI represents the base (pre-change) state. Use it
  strictly as comparison/background context to understand the codebase the
  changes are targeting. The PR/local diff is the ground truth for what is
  actually changing. When SCSI results conflict with the diff, the diff wins —
  the conflict is expected and simply means the PR modifies that code.
- Query strategy — generate questions from the diff:
  1. Read the diff to identify what changed.
  2. Generate semantic questions about the contracts, invariants, and patterns
     the changed code touches (e.g. "how is X validated elsewhere?", "what calls
     this function?", "what pattern does the codebase use for Y?").
  3. Query each question via SCSI tools against the repo index.
  4. Carry the answers as base-branch context into the review (for comparison
     and to understand surrounding code — not as current-branch truth).
- Use SCSI to learn base-branch implementation and invariants, then compare
  against the PR/local diff (ground truth).

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
- This line is reviewer metadata for the assistant's output. Do not include it
  in GitHub comment bodies.

## Truth Validation Framework

Use in every non-trivial review.

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

- CRITICAL: security vulnerability, data loss/corruption, authz/authn bypass,
  crash, or unsafe migration.
- HIGH: user-visible bug, broken invariant, serious performance regression, or
  high operational risk.
- MEDIUM: maintainability risk, unclear behavior, missing tests for a risky
  change, or non-trivial tech debt.
- LOW: small improvements, clarity, naming/style consistency (true nits).

## Draft Style (Public-Ready)

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

## Posting Boundary

- Draft in chat first.
- If the user asks to post/submit/apply anything to GitHub:
  - keep the draft content from the review mode
  - then switch to `~/.agents/skills/github/SKILL.md`
  - get explicit approval for the GitHub side effect
