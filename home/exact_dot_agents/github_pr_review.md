# GitHub PR Review Workflow

Primary goal: iterative, evidence-based review that stays focused and actionable.

Non-negotiables:
- Review in context: PR description, linked issues/PRs, all comments/threads, and the full diff.
- External truth applies: locally verify behavior under review (tests, repros, /tmp simulations) before asserting.
- Use semantic code search primarily to learn base-branch context, then compare against PR branch changes.
- Maintain a prioritized findings queue (most critical first), but present only one finding at a time; once addressed, move to the next.
- Do not implement reviewer suggestions immediately.
- Any GitHub side effect (posting comments/reviews, resolving threads) requires explicit user approval.

How to review (investigation):
1. Read the PR description fully; open and follow every reference (issues, PRs, docs).
2. Read all review threads end-to-end (including replies); note decisions, disagreements, and open questions.
3. Read the full diff; identify behavior changes, risks, and invariants that might be broken.
4. Pull semantic context:
   - Prefer semantic-code-search MCP tools (see `~/.agents/semantic_code_search.md`).
   - Use them primarily to learn base-branch context (existing patterns, invariants, related call sites), then compare against PR branch changes.
   - If needed, cross-check base-branch source with git (e.g., `git show <base>:<path>` / `git diff <base>...HEAD`) to keep the comparison grounded.
   - If the MCP tools are unavailable, use local `Grep`/`Glob`/`Read` to build equivalent context.
5. Verify locally:
   - Run the smallest sufficient tests.
   - If the concern is behavioral, reproduce it (or simulate it) in `/tmp` or the worktree.
   - Anchor conclusions in evidence (commands run, outputs observed, code locations).

Findings handling (the iterative loop):
- Keep a full internal list ordered by severity (correctness/security/data-loss > performance > UX > maintainability > style).
- Present exactly one finding at a time. For each finding, keep it concrete and include:
  - What's wrong (concrete)
  - Why it matters (impact)
  - How to verify (minimal repro/test)
  - Proposed fix (smallest change)
- Do not dump the whole list at once. After we resolve the current item, present the next.

Comment style rules (for drafts):
- Tone: direct, casual, friendly.
- No headline summaries or category prefixes (exception: `nit:` allowed only for true nits).
- Keep explanations simple; prefer tiny examples, pseudocode, or ASCII sketches over word salad.
- End every drafted comment with `Wdyt` as its final sentence.
- Always draft the comment in chat first and get approval before posting.

Where to comment:
- Default: inline in the diff (review comment on a line or range).
- Replies: post directly in the existing thread; do not quote-reply.
- Quote replies: allowed only for PR-level timeline comments.
- File-scoped concerns: prefer a file-level review comment (`subject_type=file`) instead of a PR-level comment.

Posting comments (examples; always draft + get approval first)

Inline review comment (line or range; supports ` ```suggestion ` blocks):
```
gh api repos/OWNER/REPO/pulls/NUM/comments \
  -f body=$'Text.\n\n```suggestion\ncode\n```\n\nWdyt' \
  -f commit_id=SHA -f path=FILE -f side=RIGHT -f line=LINE
```
For multi-line, add: `-f start_line=START -f start_side=RIGHT`.

File-level review comment (file-scoped, no line needed):
```
gh api repos/OWNER/REPO/pulls/NUM/comments \
  -f body=$'Text.\n\nWdyt' \
  -f commit_id=SHA -f path=FILE -f subject_type=file
```

Reply in an existing review thread (no quote reply):
```
gh api repos/OWNER/REPO/pulls/NUM/comments/COMMENT_ID/replies \
  -f body=$'Text.\n\nWdyt'
```

PR-level timeline comment (use sparingly; quote replies allowed here):
```
gh pr comment NUM -b "<text>"
```
Or:
```
gh pr review NUM --comment -b "<text>"
```

Thread resolution:
- If a concern is clearly and sufficiently addressed and does not require a reply from the commenter, resolve the thread.
- Otherwise, reply (no quotes) with what changed and why, then resolve if no follow-up is needed.

Sub-issues API:

GitHub's sub-issue API creates real parent-child relationships (not tasklists).

Create hierarchy:
1. Create child issues first with full descriptions.
2. Get GraphQL IDs:
```
gh api graphql -f query='{ repository(owner:"org",name:"repo") { issue(number:N) { id } } }'
```
3. Link:
```
gh api graphql -f query="mutation { addSubIssue(input:{issueId:\"PARENT_ID\",subIssueId:\"CHILD_ID\"}) { issue { number } } }"
```
4. Verify: `gh api repos/:owner/:repo/issues/NUM/sub_issues`

Mutations: `addSubIssue`, `removeSubIssue`, `reprioritizeSubIssue`
