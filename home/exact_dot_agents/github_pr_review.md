# GitHub PR Review Workflow

Primary goal: iterative, evidence-based review that stays focused and actionable.

Non-negotiables:

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
4. Pull semantic context:
   - Prefer semantic-code-search MCP tools (see `~/.agents/semantic_code_search.md`).
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
   - Anchor conclusions in evidence (commands run, outputs observed, code
     locations).

Findings handling (the iterative loop):

- Keep a full internal list ordered by severity
  (correctness/security/data-loss > performance > UX > maintainability > style).
- Present exactly one finding at a time. For each finding, keep it concrete
  and include:
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

Where to comment:

- Default: inline in the diff (review comment on a line or range).
- Replies: post directly in the existing thread; do not quote-reply.
- Quote replies: allowed only for PR-level timeline comments.
- File-scoped concerns: prefer a file-level review comment
  (`subject_type=file`) instead of a PR-level comment.

Posting comments (examples)

Newlines in `gh api` comment bodies:

- These examples use bash/zsh `$'...'` so `\n` becomes real line breaks.
- Do NOT do `-f body="line1\\n\\nline2"`; `gh api` will send literal `\n`
  characters and GitHub will store them verbatim.

Inline review comment (line or range; supports GitHub suggestion blocks):

~~~bash
gh api repos/OWNER/REPO/pulls/NUM/comments \
  -f body=$'Text.\n\n```suggestion\ncode\n```\n\nWdyt' \
  -f commit_id=SHA -f path=FILE -f side=RIGHT -f line=LINE
~~~

For multi-line, add: `-f start_line=START -f start_side=RIGHT`.

File-level review comment (file-scoped, no line needed):

```bash
gh api repos/OWNER/REPO/pulls/NUM/comments \
  -f body=$'Text.\n\nWdyt' \
  -f commit_id=SHA -f path=FILE -f subject_type=file
```

Reply in an existing review thread (no quote reply):

```bash
gh api repos/OWNER/REPO/pulls/NUM/comments/COMMENT_ID/replies \
  -f body=$'Text.\n\nWdyt'
```

PR-level timeline comment (use sparingly; quote replies allowed here):

```bash
gh pr comment NUM -b "<text>"
```

Or:

```bash
gh pr review NUM --comment -b "<text>"
```

Thread resolution:

- If a concern is clearly and sufficiently addressed and does not require a
  reply from the commenter, resolve the thread.
- Otherwise, reply (no quotes) with what changed and why, then resolve if no
  follow-up is needed.
