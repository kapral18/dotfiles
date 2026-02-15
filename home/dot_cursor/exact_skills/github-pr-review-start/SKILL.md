---
name: github-pr-review-start
description: "Initial GitHub PR review (first pass, no prior engagement): build a full findings queue, then draft a batch of pending inline comments and an optional summary review comment. If the user doesn't specify a PR, assume the current branch PR (infer via `gh prw --number`). Draft-only by default (do not post). Do NOT use for replying to existing threads or when the user wants one comment at a time."
---

# GitHub PR Review - Start (Batch Draft)

Primary goal: produce a high-signal initial review in one pass without posting anything.

When NOT to use:

- The user wants to reply to existing review threads one-by-one: use `github-pr-review-reply`.
- The user wants interactive iteration with exactly one comment at a time: use `github-pr-review`.

Non-negotiables:

- Review in context: PR description, linked issues/PRs, all comments/threads, and the full diff.
- Treat screenshots/GIFs/videos as first-class evidence: open every inline image/attachment in the PR description and comment threads.
- External truth applies: locally verify behavior under review (tests, repros, /tmp simulations) before asserting.
- Do not implement reviewer suggestions immediately.
- Do not post to GitHub unless explicitly asked.
- Assume the user started the agent inside the intended worktree/session already.
  - Do not create/switch worktrees proactively.
  - If the user explicitly asks to create/switch a worktree, use `~/.agents/skills/w-workflow/SKILL.md` and prefer `,w`.

Workflow:

0. Resolve the PR target (avoid searching):
   - If the user provided a PR URL/number, use that.
    - Otherwise, assume they mean the PR for the current branch:
      - `gh prw --url`
      - `gh prw --number`
    - If that fails (no PR for current branch / wrong repo / not authenticated), ask for the PR URL.

1. Do a complete pass:
   - PR description + all links
   - all threads
   - full diff
   - (if available) local verification
2. Build a complete internal findings queue ordered by severity.
3. Draft a batch of pending comments.

Coverage checklist (don’t skip): security issues, logic/correctness, data-loss risk,
performance regressions, test gaps, documentation gaps, maintainability/complexity,
and true nits.

Severity definitions (internal only; do not prefix comments with these):

- CRITICAL: security vulnerability, data loss/corruption, authz/authn bypass, crash, or unsafe migration.
- HIGH: user-visible bug, broken invariant, serious performance regression, or high operational risk.
- MEDIUM: maintainability risk, unclear behavior, missing tests for a risky change, or non-trivial tech debt.
- LOW: small improvements, clarity, naming/style consistency (true nits).

Output contract:

- Return a "Pending review draft" containing:
  - `inline_comments`: list of draft comments (one per finding worth commenting), each with:
    - Where (file path + line/range when possible)
    - Comment body (end with `Wdyt`)
    - Why it matters (1-2 lines)
    - How to verify (minimal)
    - Proposed fix (smallest change)
  - `summary_comment` (optional): a short PR-level comment (end with `Wdyt`)

Draft persistence:

- If the user says "consult before sending", keep the full batch draft in a
  single scratch file under `/tmp/` (so it can be reviewed/edited before
  posting). Do not post until explicitly asked.

Comment style rules:

- Tone: direct, casual, friendly.
- No headline summaries or category prefixes (exception: `nit:` allowed only for true nits).
- Keep explanations simple; prefer tiny examples, pseudocode, or ASCII sketches.
- End every drafted comment with `Wdyt` as its final sentence.
- Treat drafted comments as public-ready communication:
  - Do not mention internal tooling, agents, APIs, rate limits, JSON payloads, or error codes.
  - Do not include meta like “draft/pending review” in the comment body unless the user explicitly wants that.
  - If you need to reference a nearby source line, include a deep link; don’t explain why you’re linking.
  - Avoid redundant "Ref:" links when the comment is already attached to the exact line.
  - Keep claims honest: separate what you observed (evidence) vs what you infer (hypothesis)
    vs what you recommend (action).
  - Use ```suggestion``` blocks only when you are confident the replacement matches the exact
    anchored line(s); otherwise, prefer a short nudge.

If explicitly asked to POST the batch as a draft (PENDING) review:

- Use `~/.agents/skills/github-gh-workflow/SKILL.md` (section: "PR review side effects (draft / pending reviews)")
  for the exact API flow and verification.
- If you want a review summary body, include it explicitly when submitting the
  pending review (regardless of whether the event is COMMENT or APPROVE) so it
  does not get dropped.
