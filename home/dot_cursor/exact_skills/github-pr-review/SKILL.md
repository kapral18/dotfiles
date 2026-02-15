---
name: github-pr-review
description: "Interactive GitHub PR review (non-batch): read PR description/threads/diff, inspect screenshots/GIFs, verify locally, and draft exactly one actionable comment at a time. If the user doesn't specify a PR, assume the current branch PR (infer via `gh prw --number`). Use for follow-up/iterative reviews when you want to discuss and submit comments one-by-one. Do NOT use for initial batch reviews or reply-only thread iteration."
---

# GitHub PR Review Workflow

Primary goal: iterative, evidence-based review that stays focused and actionable.

When NOT to use:

- The user wants the initial review drafted in one go (batch of pending comments): use `github-pr-review-start`.
- The user is replying to existing review threads: use `github-pr-review-reply`.

Non-negotiables:

- Resolve the PR target (avoid searching):
  - If the user provided a PR URL/number, use that.
  - Otherwise, assume they mean the PR for the current branch:
    - `gh prw --url`
    - `gh prw --number`
  - If that fails (no PR for current branch / wrong repo / not authenticated), ask for the PR URL.
- Review in context: PR description, linked issues/PRs, all comments/threads,
  and the full diff.
- Treat screenshots/GIFs/videos as first-class evidence: open every inline
  image/attachment in the PR description and comment threads (Before/After,
  repro recordings, logs-as-images). Do not accept claims that depend on
  visuals without inspecting them; if they’re missing or unclear, ask for
  visuals.
- External truth applies: locally verify behavior under review (tests, repros,
  /tmp simulations) before asserting.
- Use semantic code search primarily to learn base-branch context, then
  compare against PR branch changes.
- Maintain a prioritized findings queue (most critical first).
- Do not implement reviewer suggestions immediately.
- Any GitHub side effect (posting comments/reviews, resolving threads)
  requires explicit user approval.
- Assume the user started the agent inside the intended worktree/session already.
  - Do not create/switch worktrees proactively.
  - If the user explicitly asks to create/switch a worktree, use `~/.agents/skills/w-workflow/SKILL.md` and prefer `,w`.

How to review (investigation):

1. Read the PR description fully; open and follow every reference recursively
   until nothing left to open and investigate more (issues, PRs, docs).
   - Open and inspect any embedded screenshots/GIFs/videos and attachments.
2. Read all review threads end-to-end (including replies); note decisions,
   disagreements, and open questions.
   - Open and inspect screenshots/GIFs/videos referenced in comments and
     replies (don’t rely on alt text or one-line descriptions).
3. Read the full diff; identify behavior changes, risks, and invariants that
   might be broken.
   - Coverage checklist (don’t skip): security issues, logic/correctness, data-loss risk,
     performance regressions, test gaps, documentation gaps, maintainability/complexity,
     and true nits.
4. Pull semantic context:
   - Prefer semantic-code-search MCP tools (see `~/.agents/skills/semantic-code-search/SKILL.md`).
   - Use them primarily to learn base-branch context (existing patterns,
     invariants, related call sites), then compare against PR branch changes.
   - If needed, cross-check base-branch source with git (e.g., `git show <base>:<path>`
     or `git diff <base>...HEAD`) to keep the comparison grounded.
   - If the MCP tools are unavailable, use local `Grep`/`Glob`/`Read` to
     build equivalent context.
5. Verify locally:
   - Run the smallest sufficient tests.
   - If the concern is behavioral, reproduce it (or simulate it) in `/tmp` or
     the worktree.
   - UI repro hygiene (when verifying UI/editor behavior):
     - Do one claim per repro run; reset state between runs (reload/new tab).
     - Ensure inputs are cleared deterministically before typing.
     - For rich editors (e.g. Monaco), do not assume the accessible textarea
       value reflects the full editor model; verify what is actually rendered
       (and capture screenshots/GIFs as evidence).
   - Anchor conclusions in evidence (commands run, outputs observed, code
     locations).

Findings handling (the iterative loop):

- Keep a full internal list ordered by severity
  (correctness/security/data-loss > performance > UX > maintainability > style).

Severity definitions (internal only; do not prefix comments with these):

- CRITICAL: security vulnerability, data loss/corruption, authz/authn bypass, crash, or
  unsafe migration.
- HIGH: user-visible bug, broken invariant, serious performance regression, or high
  operational risk.
- MEDIUM: maintainability risk, unclear behavior, missing tests for a risky change, or
  non-trivial tech debt.
- LOW: small improvements, clarity, naming/style consistency (true nits).

- Present exactly one finding at a time. For each finding, keep it concrete
  and include:
  - Where (file path + line/range when possible)
  - What's wrong (concrete)
  - Why it matters (impact)
  - How to verify (minimal repro/test)
  - Proposed fix (smallest change)
- Do not dump the whole list at once. After we resolve the current item,
  present the next.

Comment style rules (for drafts):

- Tone: direct, casual, friendly.
- No headline summaries or category prefixes (exception: `nit:` allowed only
  for true nits).
- Keep explanations simple; prefer tiny examples, pseudocode, or ASCII
  sketches over word salad.
- End every drafted comment with `Wdyt` as its final sentence.
- Always draft the comment in chat first.
- Treat drafted comments as public-ready communication:
  - Do not mention internal tooling, agents, APIs, rate limits, JSON payloads, or error codes.
  - Do not say “can’t anchor inline” / “not in diff hunks”. If you need to point to a nearby
    location, provide a precise source link and keep the language user-facing.
  - Avoid redundant "Ref:" links when the comment is already attached to the exact line.
  - Keep claims honest: separate what you observed (evidence) vs what you infer (hypothesis)
    vs what you recommend (action).
  - Avoid quoting hard limits/constraints unless you verified they apply to the specific field/API.
  - Use ```suggestion``` blocks only when you are confident the replacement matches the exact
    anchored line(s); otherwise, prefer a short nudge.

Where to comment:

- Default: inline in the diff (review comment on a line or range).
- Replies: post directly in the existing thread; do not quote-reply.
- Quote replies: allowed only for PR-level timeline comments.
- File-scoped concerns: prefer a file-level review comment
  (`subject_type=file`) instead of a PR-level comment.

Inline comment anchoring (diff vs “clickable UI lines”):

- PR review comments are anchored to the PR’s unified diff. In practice, this
  means you must provide a location GitHub can resolve *against the PR diff for
  the specific commit*.
- The GitHub UI can make a line “clickable” (commentable) even when it’s not a
  changed line by showing/expanding diff context. The UI also computes the
  correct diff anchor automatically.
- For API calls, do not assume a source-file line number is a valid anchor.
  Prefer one of these approaches:
  - Use `position` (diff-relative). GitHub documents exactly how to compute it:
    it’s the 1-based count of lines from the first `@@` hunk header in that file
    within the PR diff (continues across whitespace and subsequent hunks until
    the next file).
  - Or use `line` + `side` / `start_line` + `start_side` (still must resolve
    against the PR diff; GitHub will 422 if it cannot resolve).
- If the specific source line you care about is not shown in the diff context,
- If the specific source line you care about is not shown in the diff context,
  do NOT anchor the comment to an unrelated line. Anchor on the nearest
  relevant diff line in the same file and include a deep link to the exact
  source location on the PR head SHA.
- If you cannot find a relevant diff anchor without confusing the author,
  do not force an inline comment. Use a file-level comment (`subject_type=file`)
  or a PR-level comment that links to the exact source lines.
- If you truly need a file-scoped comment and it’s okay for it to be immediately
  visible, use a file-level review comment (`subject_type=file`).

Deep links to exact source lines (PR head SHA):

- Prefer links of the form:
  `https://github.com/OWNER/REPO/blob/<head_sha>/<path>#L<start>-L<end>`
- If the GitHub “contents” API is unavailable/unreliable for the file, fetch the
  PR head commit locally and use `git show <head_sha>:<path>` to compute line
  numbers for the link.

Posting (GitHub side effects)

- This skill is for reviewing and drafting.
- If you are explicitly asked to post comments/reviews to GitHub, use `~/.agents/skills/github-gh-workflow/SKILL.md`.

Thread resolution:

- If a concern is clearly and sufficiently addressed and does not require a
  reply from the commenter, resolve the thread.
- Otherwise, reply (no quotes) with what changed and why, then resolve if no
  follow-up is needed.
