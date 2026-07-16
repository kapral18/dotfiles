# GitHub PR Comments — Posting Examples

Reference for the `k-github` skill.
Load when posting inline, file-level, reply, or PR-timeline comments outside the draft-review batch flow.

- Use bash/zsh `$'...'` so `\n` becomes real line breaks. Do NOT send literal `\n`.
- Add a soft close such as `Wdyt` only when the review style calls for it.
- **Commit references in comment bodies must be clickable links, never bare hashes or backtick-wrapped hashes.**
  Use the full GitHub URL: `https://github.com/OWNER/REPO/commit/FULL_SHA` (or `/pull/NUM/commits/FULL_SHA` for PR commits).
  Resolve `OWNER/REPO` from the current repo and expand short hashes to full SHA before linking.
- Follow the relevant PR review mode for anchoring and comment placement:
  - `~/.agents/skills/k-review/references/pr_review.md`
  - `~/.agents/skills/k-review/references/pr_fix.md`
- For UI-related comments, replies, or PR-level feedback drafted after `/agent-review` or `live-ui-review`, require screenshot handoff evidence outside the body or a valid blocker/non-applicability reason.
  Never put local screenshot paths in GitHub comment, reply, review, or PR-level bodies.
  Show folder-open/provided status in the approval/preflight handoff.

## Inline review comment (line or range; supports GitHub suggestion blocks)

````bash
gh api repos/OWNER/REPO/pulls/NUM/comments \
  -f body=$'Text.\n\n```suggestion\ncode\n```' \
  -f commit_id=SHA -f path=FILE -f side=RIGHT -f line=LINE
````

For multi-line, add: `-f start_line=START -f start_side=RIGHT`.

## File-level review comment (file-scoped, immediately visible)

```bash
gh api repos/OWNER/REPO/pulls/NUM/comments \
  -f body=$'Text.' \
  -f commit_id=SHA -f path=FILE -f subject_type=file
```

## Reply in an existing review thread (no quote reply)

```bash
# Threaded replies are represented as regular PR review comments with `in_reply_to_id`,
# and there is no working `/pulls/comments/{comment_id}/replies` endpoint here (404).
#
# Use the PR review comment create endpoint with `in_reply_to`:
gh api repos/OWNER/REPO/pulls/NUM/comments \
  -f body=$'Text.' \
  -F in_reply_to=COMMENT_ID
```

Notes:

- The request field is `in_reply_to` (integer). The response field is `in_reply_to_id`.
- Do NOT use `in_reply_to_id` in the request; it may create a new top-level comment instead of a reply.
- If you need to add query params to a GET `gh api` call, use `-X GET`.
  In practice, adding `-f` or `-F` without `-X GET` can cause `gh` to hit the POST schema by default.
- zsh gotcha: avoid unquoted `?ref=...` in endpoints (it can trigger `no matches found`).
  Prefer: `gh api -X GET repos/OWNER/REPO/contents/PATH -F ref=main`
- If you _are_ posting an anchored comment that requires `commit_id`, and GitHub rejects it as "commit_id is not part of the pull request", use the `commit_id` from the target review comment you're replying to.

## PR-level timeline comment (use sparingly)

```bash
gh pr comment NUM -b "<text>"
```

Or:

```bash
gh pr review NUM --comment -b "<text>"
```
