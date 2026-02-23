# GitHub + gh Playbook

Defaults & constraints:

- Use `gh` CLI for GitHub activity.
- Follow repository merge settings (squash/rebase/merge); do not enforce a
  merge strategy.
- Never merge into the base branch via CLI; merges happen via the GitHub UI.
- For non-interactive reliability, set `GH_PAGER=cat` for all `gh` calls.

PR targeting (avoid searching):

- If the user did not specify a PR URL/number, assume they mean the PR for the
  current branch in the current repo.
- Resolve the PR number/URL with:
  - `,gh-prw --number`
  - `,gh-prw --url`
- If `,gh-prw` fails once, stop and ask for the PR URL (or use `-R OWNER/REPO` if
  the user clearly intends a different repo).

When NOT to use:

- The user wants to draft PR/issue text only (draft-only): use the compose playbooks.
  - PR (general): `~/.agents/playbooks/github/compose_pr_general.md`
  - PR (Elastic/Kibana): `~/.agents/playbooks/github/compose_pr_elastic.md`
  - Issue (general): `~/.agents/playbooks/github/compose_issue_general.md`
  - Issue (Elastic/Kibana): `~/.agents/playbooks/github/compose_issue_elastic.md`
- The user wants PR review feedback:
  - Use: `~/.agents/playbooks/review/router.md`
  - It routes between local vs PR review, and PR modes (start/iterative/replies).
- The user wants local git operations (status/diff/commit/rebase): `~/.agents/playbooks/git/workflow.md`.
- The user wants worktree management (create/switch/remove worktrees): `~/.agents/playbooks/worktrees/w_workflow.md`.

Approvals:

- Any GitHub side effect requires explicit approval unless the user instructed
  otherwise.
  Examples (non-exhaustive): create/edit PRs or issues, post comments/reviews,
  apply metadata (labels/assignees/milestones/projects), merge, or create
  releases.

PR review side effects (draft / pending reviews):

- Creating a PENDING (draft) PR review requires the reviews API. Omit `event` in:
  `POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews`
- Batch draft comments: include all inline review comments in the `comments` array
  in that same request.
- Practical constraint: GitHub generally allows only one `PENDING` review per
  user per PR. If you need to change bodies/anchors, delete the pending review
  and recreate it.
- Pending inline review comments are not practically editable via API; do not
  waste time trying to PATCH. Delete the pending review and recreate it with the
  corrected payload.
- Do not try to attach comments to an already-created pending review via the PR
  comments endpoint (it won't accept `pull_request_review_id`). If you need to
  change anchors/bodies, delete the pending review and recreate it.
- File-level review comments (`subject_type=file`) are immediately visible; they
  are not part of a pending review. In practice, while you have a pending
  review, you may not be able to create additional file-level review comments
  from the same user.
- Arrays: prefer `gh api ... --input /path/to.json` for payloads containing arrays
  (avoids accidentally sending arrays as strings via `-f/-F`).

If explicitly asked to POST a batch as a draft (PENDING) review:

- Create a single PR review in `PENDING` state by omitting `event` when calling:
  `POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews`
- Include all inline comments in the `comments` array in that same request.
- Every inline comment must resolve to a valid diff anchor.
  - Prefer `position` (diff-relative). Compute it from the PR's unified diff.
  - If a file has multiple hunks (or repeated target lines), create separate comments and compute the correct anchor per hunk/occurrence.
- Keep the review summary body empty unless the user explicitly wants a public summary.

After submitting, verify what actually posted:

- The submitted review body is whatever you submit with the final event call.
  If you want a summary, include it explicitly when submitting (COMMENT/APPROVE/REQUEST_CHANGES).
- For COMMENT/REQUEST_CHANGES, treat the body as required: always include it.
- UI gotcha: switching the event type (e.g. Comment -> Approve) can drop the typed
  summary text in some flows. For API-based submission, prevent this by always
  sending the intended `body` with the submit request.
- Count posted inline comments and reconcile anything missing; if needed, post
  a follow-up (non-batch) comment with leftover deep links.

Example (create a pending review with many draft comments):

```bash
cat > /tmp/review-payload.json <<'JSON'
{
  "commit_id": "HEAD_SHA",
  "body": "",
  "comments": [
    { "path": "path/to/file.ts", "position": 6, "body": "Comment text.\n\nWdyt" },
    { "path": "path/to/file.ts", "position": 19, "body": "Another comment.\n\nWdyt" }
  ]
}
JSON

gh api repos/OWNER/REPO/pulls/NUM/reviews -X POST --input /tmp/review-payload.json

# Verify:
# - Confirm the review is PENDING:
#   gh api repos/OWNER/REPO/pulls/NUM/reviews --jq '.[] | {id,state}'
# - Confirm pending review has N draft comments:
#   gh api repos/OWNER/REPO/pulls/NUM/reviews/REVIEW_ID/comments --jq 'length'
# - Confirm visible PR review comments are still empty (until submission):
#   gh api repos/OWNER/REPO/pulls/NUM/comments --jq 'length'

# Submit later (include body explicitly if you want a summary):
# gh api repos/OWNER/REPO/pulls/NUM/reviews/REVIEW_ID/events -X POST -f event=APPROVE -f body=$'Looks good.\n\nWdyt'
```

Posting PR review comments (examples):

- Use bash/zsh `$'...'` so `\n` becomes real line breaks. Do NOT send literal `\n`.
- Follow the relevant PR review mode playbook for anchoring and comment placement behavior:
  - `~/.agents/playbooks/review/pr_start.md`
  - `~/.agents/playbooks/review/pr_iterative.md`
  - `~/.agents/playbooks/review/pr_reply.md`

Inline review comment (line or range; supports GitHub suggestion blocks):

````bash
gh api repos/OWNER/REPO/pulls/NUM/comments \
  -f body=$'Text.\n\n```suggestion\ncode\n```\n\nWdyt' \
  -f commit_id=SHA -f path=FILE -f side=RIGHT -f line=LINE
````

For multi-line, add: `-f start_line=START -f start_side=RIGHT`.

File-level review comment (file-scoped, immediately visible):

```bash
gh api repos/OWNER/REPO/pulls/NUM/comments \
  -f body=$'Text.\n\nWdyt' \
  -f commit_id=SHA -f path=FILE -f subject_type=file
```

Reply in an existing review thread (no quote reply):

```bash
# Threaded replies are represented as regular PR review comments with `in_reply_to_id`,
# and there is no working `/pulls/comments/{comment_id}/replies` endpoint here (404).
#
# Use the PR review comment create endpoint with `in_reply_to`:
gh api repos/OWNER/REPO/pulls/NUM/comments \
  -f body=$'Text.\n\nWdyt' \
  -F in_reply_to=COMMENT_ID
```

Notes:

- The request field is `in_reply_to` (integer). The response field is `in_reply_to_id`.
- Do NOT use `in_reply_to_id` in the request; it may create a new top-level comment instead of a reply.
- If you need to add query params to a GET `gh api` call, use `-X GET`.
  In practice, adding `-f` or `-F` without `-X GET` can cause `gh` to hit the POST schema by default.
- zsh gotcha: avoid unquoted `?ref=...` in endpoints (it can trigger `no matches found`). Prefer:
  `gh api -X GET repos/OWNER/REPO/contents/PATH -F ref=main`
- If you *are* posting an anchored comment that requires `commit_id`, and GitHub rejects it as
  "commit_id is not part of the pull request", use the `commit_id` from the target review comment you're replying to.

PR-level timeline comment (use sparingly):

```bash
gh pr comment NUM -b "<text>"
```

Or:

```bash
gh pr review NUM --comment -b "<text>"
```

PR creation:

- Create PRs as draft by default.
- Always ask which existing issue the PR should reference (do not invent issue
  numbers).
- Ask the user whether the PR should `Closes #X` or `Addresses #X` before
  creating the PR.
- If there is no existing issue, stop and ask whether to create one; do NOT
  create issues unless the user explicitly instructs you to.
- PR title is a human-readable change summary (not necessarily the
  Conventional Commit header).
- Multiline bodies/comments: use bash/zsh `$'...'` so `\n` becomes real
  newlines. Do NOT rely on `\\n` escapes inside normal quotes when using
  `gh api -f body=...`.
- Test plan is inferred from the change surface; run the smallest sufficient
  set of checks and record the commands/results in the PR.
- Always propose labels/assignees/milestone/projects first and get explicit
  confirmation before applying any of them.

Composition (draft-only) guidance:

- Draft PR bodies using:
  - General repos: `~/.agents/playbooks/github/compose_pr_general.md`
  - Elastic/Kibana repos: `~/.agents/playbooks/github/compose_pr_elastic.md`
- Draft issue bodies using:
  - General repos: `~/.agents/playbooks/github/compose_issue_general.md`
  - Elastic/Kibana repos: `~/.agents/playbooks/github/compose_issue_elastic.md`
- Label proposals for Elastic/Kibana (propose-only): `~/.agents/playbooks/github/labels_propose_elastic_kibana.md`
- Kibana Management ownership hints: `~/.agents/playbooks/kibana/management_ownership.md`

Do not add/modify repo `.github/*` templates unless the user explicitly asks.

Sub-issues API:

GitHub's sub-issue API creates real parent-child relationships (not tasklists).

Create hierarchy:

1. Create child issues first with full descriptions.
2. Get GraphQL IDs:

```bash
gh api graphql -f query='{ repository(owner:"org",name:"repo") { issue(number:N) { id } } }'
```

3. Link:

```bash
gh api graphql -f query="mutation { addSubIssue(input:{issueId:\"PARENT_ID\",subIssueId:\"CHILD_ID\"}) { issue { number } } }"
```

4. Verify: `gh api repos/:owner/:repo/issues/NUM/sub_issues`

Mutations: `addSubIssue`, `removeSubIssue`, `reprioritizeSubIssue`
