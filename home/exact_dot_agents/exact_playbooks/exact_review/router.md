# Review Router

Goal:

- route "review" requests to the smallest correct mode playbook (natural discovery)
- keep shared review rules always loaded, while mode details are lazy-loaded

Contract:

- This router is the entrypoint. If another playbook points you here for shared
  rules, you may skip routing and jump to the relevant section.
- After you select a mode, open exactly one mode file and follow it:
  - `~/.agents/playbooks/review/local_changes.md`
  - `~/.agents/playbooks/review/pr_start.md`
  - `~/.agents/playbooks/review/pr_iterative.md`
  - `~/.agents/playbooks/review/pr_reply.md`
- Do not load `~/.agents/playbooks/github/gh_workflow.md` for read-only PR
  inspection/review. Only load it when the user explicitly asks to post/submit
  anything to GitHub.

## PR Detection (Do First When PR Is Involved)

If the user mentions or strongly implies a PR (PR/pull request, PR review,
threads, "check my PR comment", "recheck this fix from the PR", etc.):

- First step is PR discovery via `gh prw` (read-only):
  - `GH_PAGER=cat gh prw --number`
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
- Then open: `~/.agents/playbooks/review/pr_reply.md`

Mode: PR iterative (one new comment at a time)

- Use when: the user wants one new top-level review comment per turn for a PR
  ("what's the next comment", "continue the review", "one comment at a time").
- Then open: `~/.agents/playbooks/review/pr_iterative.md`

Mode: PR start (initial batch draft)

- Use when: the user wants an initial full PR review drafted in one go, or the
  user provides a PR URL/number and says "review" without asking for reply-only
  or one-at-a-time.
- Also use when: the user asks you to recheck/verify whether a PR fix resolves a
  bug ("does this PR fix it", "can you recheck", "verify this fix", "check my
  comment", "is it resolved on the updated branch").
- Then open: `~/.agents/playbooks/review/pr_start.md`

Mode: local changes review (working tree or branch delta)

- Use when: the user asks to review local changes/diff, or when there is no PR
  for the current branch and the user still wants a review.
- Then open: `~/.agents/playbooks/review/local_changes.md`

If the user's intent is still unclear, resolve via local context (do not guess):

- If not in a git repo:
  - Ask: "Is this a GitHub PR review (send URL/number), or a local repo changes
    review?"
- If in a git repo:
  - Run `git status --porcelain=v1 -b` (read-only, do not ask to proceed).
  - If staged/unstaged changes exist: local changes mode.
  - If working tree is clean:
    - Try PR discovery via `gh prw` (read-only):
      - `GH_PAGER=cat gh prw --number`
    - If a PR is found: PR start mode.
    - If no PR is found: local changes mode (branch delta).

Ambiguity rule:

- If both a PR exists and the working tree has local changes and the user just
  says "review", ask:
  "Should I review the local working tree diff, or the GitHub PR diff/threads?"
  Default: local working tree first.

## Shared Rules (All Modes)

Read-only probes:

- Start read-only investigation immediately. Do not ask for confirmation before
  read-only `git`/`gh` checks.

Hard constraints:

- External truth applies: verify behavior under review (tests, repros, `/tmp`
  simulations) before asserting when practical.
- Do not implement fixes while reviewing.
- Do not post to GitHub, submit reviews, apply labels, or resolve threads unless
  explicitly asked.
- Assume the user started the agent inside the intended repo/worktree/session:
  - do not create/switch worktrees proactively
  - if the user explicitly asks to create/switch a worktree, use
    `~/.agents/playbooks/worktrees/w_workflow.md` and prefer `,w`

Base-branch context (mandatory when applicable):

- Goal: compare the diff against how base (usually `main`) works today.
- If semantic code search is available and the repo is indexed:
  - Load and follow: `~/.agents/playbooks/code_search/semantic_code_search.md`
  - Use it to understand the base-branch implementation and invariants, then
    compare against the PR/local diff.
- If semantic code search is unavailable or the repo is not indexed:
  - Use local sources instead:
    - `rg` + file reads
    - `git show <base>:<path>` for base-branch behavior
    - `git diff <base>...HEAD` for branch delta

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
- End every drafted comment/reply with `Wdyt` as its final sentence.
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
- Use `suggestion` blocks only when confident the replacement matches the
  exact anchored line(s).

Posting boundary:

- Draft in chat first.
- If the user asks to post/submit/apply anything to GitHub:
  - keep the draft content from the review mode playbook
  - then switch to `~/.agents/playbooks/github/gh_workflow.md`
  - get explicit approval for the GitHub side effect
