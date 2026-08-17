# GitHub PR Reviews — Draft / Pending Review Mechanics

Reference for the `k-github` skill. Load when creating, reconciling, or submitting a PR review (draft/pending or published).

> **CRITICAL — pending vs published reviews:**
>
> - When the user says "pending review", "draft review", or "post pending": the
>   review MUST stay in `PENDING` state (visible only to you, not the PR
>   author).
> - **NEVER include `event` in the create-review payload.** If you include
>   `"event": "COMMENT"` (or `APPROVE` / `REQUEST_CHANGES`), the review is
>   **immediately and irreversibly published** to the PR author and all
>   subscribers.
> - The default behavior of `POST /reviews` **without** `event` is `PENDING`.
>   That is the only safe way to create a draft review.
>
> **Pre-flight checklist (mandatory before every review POST or submit):**
>
> 1. Read back the JSON payload you are about to send.
> 2. Confirm the `event` key is **absent** from the create-review payload.
> 3. If `event` is present in the create-review payload, **remove it** before sending.
> 4. Only add `event` in a **separate** submit call after the user explicitly
>    asks to publish.
> 5. Before that submit call, show the exact submit `event` and PR-level review
>    `body` alongside the inline-comment payload; submit only the exact approved
>    summary body, never an invented or revised one.
> 6. For code-review feedback, default to inline anchored `comments[]` (not body-only summary),
>    unless the user explicitly asks for PR-level summary feedback.
> 7. In `body` and each inline comment body,
>    any code/file/symbol reference must be a clickable source link (exact file + line/range on PR head SHA), not plain text.
> 8. Fetch the current PR diff/patch for the target head SHA and verify every `line`/`side`, range, or
>    `position` anchor is inside the intended diff hunk immediately before creating or submitting the review.
>    Verify against the fresh diff, since full-file line numbers, stale patches, and memory drift out of sync.
> 9. Read existing current-account pending reviews and reconcile them with the payload so review feedback stays consolidated, never fragmented.
> 10. For UI-related review feedback drafted after `/k-deep-review` or `live-ui-review`, verify the approved draft includes `ui_evidence_attachments` or a valid blocker/non-applicability reason.
>     Keep local screenshot paths out of `body` and inline comment bodies; show the handoff separately in the approval payload.

- Definition: a "pending review" is a PR review whose API `state` is `PENDING`.
  It is visible only to the reviewer who created it until submission (COMMENT/APPROVE/REQUEST_CHANGES), and it does not appear to the PR author as posted review comments while pending.
- Creating a PENDING (draft) PR review requires the reviews API. Omit `event` in: `POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews`
- Batch draft comments: include all inline review comments in the `comments` array in that same request.
- Practical constraint: GitHub generally allows only one `PENDING` review per user per PR.
- Adding net-new comments to an existing pending review does not require delete/recreate;
  append them with GraphQL `addPullRequestReviewThread` (see below).
- Delete/recreate is only required to change or remove existing draft comments;
  they are not PATCH-editable, so delete/recreate is the only edit path.
- Append to a pending review only via GraphQL: REST `POST /pulls/{n}/comments` returns `422 user_id can only have one pending review per pull request`, and `/pulls/{n}/reviews/{review_id}/comments` is GET-only (no POST exists).
- File-level review comments (`subject_type=file`) are immediately visible; they are not part of a pending review.
  In practice, while you have a pending review, you may not be able to create additional file-level review comments from the same user.
- Verification rule of thumb:
  - `GET /repos/{o}/{r}/pulls/{n}/reviews` will show the `PENDING` review
  - `GET /repos/{o}/{r}/pulls/{n}/comments` should remain unchanged until you submit (draft comments are attached to the review, not publicly posted)
- Arrays: prefer `gh api ... --input /path/to.json` for payloads containing arrays (avoids accidentally sending arrays as strings via `-f/-F`).

## Existing pending-review merge guard

- Before any create, delete/recreate, or submit action for a PR review:
  1. Resolve the current login: `gh api user --jq '.login'`.
  2. List reviews: `gh api --paginate repos/OWNER/REPO/pulls/NUM/reviews`.
  3. For each review with `state == "PENDING"` and `user.login` matching the current login, read draft comments:
     `gh api --paginate repos/OWNER/REPO/pulls/NUM/reviews/REVIEW_ID/comments`.
  4. Compare the pending review body/comments against the approved draft from `k-review`/`k-deep-review` and its `Pending review reconciliation:` ledger.
  5. If any approved review feedback is UI-related and drafted after `/k-deep-review` or `live-ui-review`, compare it against the draft's `ui_evidence_attachments` ledger and block if screenshot evidence is missing without a valid blocker/non-applicability reason.
- If no reconciliation ledger exists, run the review skill's Existing Pending Review Reconciliation before mutating GitHub.
- If a pending review exists and the new payload is purely **additive** (net-new findings, no edits to existing draft comments):
  - keep the single existing pending review (create/delete/recreate stays off the table)
  - append the net-new threads via GraphQL `addPullRequestReviewThread` against the existing `pullRequestReviewId`
  - show the exact pending review ID, the net-new comment bodies/anchors, and wait for explicit approval before posting
- If the new payload must **change or drop** existing draft comments:
  - prepare one consolidated payload that keeps still-valid pending findings and adds net-new findings exactly once
  - show the exact old pending review ID, comments to keep/drop, new payload, and delete/recreate action; wait for explicit approval
- If submitting an existing pending review:
  - fetch the pending review and comments immediately before the submit call
  - verify they match the approved reconciled payload and current head anchors
  - if they differ, stop and ask for approval to replace/reconcile first
- If a pending review contains stale or contradictory feedback, replace it instead of submitting it:
  delete/recreate only after explicit approval with the consolidated replacement payload.

## Posting a batch as a draft (PENDING) review

If explicitly asked to POST a batch as a draft (PENDING) review:

- Create a single PR review in `PENDING` state by omitting `event` when calling: `POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews`
- Include all inline comments in the `comments` array in that same request.
- Every inline comment must resolve to a valid diff anchor.
- Fetch the current PR diff/patch immediately before posting and verify every anchor against the current hunk.
- Prefer `line`/`side` anchoring over `position` (less error-prone):
  - Use `line` (the file line number on the right side) + `side: "RIGHT"`.
  - For left-side-only comments, use `side: "LEFT"` + the old-file line number.
  - For multi-line ranges, add `start_line` + `start_side`.
  - The `line`/`side` approach uses absolute file line numbers (visible in the GitHub diff UI), so there is no off-by-one math to get wrong.
- If you must use `position` (diff-relative, 0-indexed from the `@@` header):
  - Fetch the file's `patch` from `GET /repos/{o}/{r}/pulls/{n}/files`.
  - Split by newlines. The `@@` hunk header at index 0 = position 0 (not a valid comment target).
    The first content line at index 1 = position 1.
  - In short: the 0-based array index of the split **is** the position value.
  - If a file has multiple hunks (or repeated target lines), create separate comments and verify the correct hunk/occurrence.
  - Common trap: the patch changes when new commits are pushed.
    Always re-fetch the patch from the current PR head before computing positions.
- Keep the pending review summary body empty; fill it only when the user explicitly wants a public summary.

## Embedding screenshot images in review comments

Upload mechanics, URL harvesting, and image/video layout rules are generic and live in `~/.agents/skills/k-github/references/attachments.md` — load that reference first.
Review-specific rules on top of it:

- Use this flow when the user approves attaching local screenshots to review feedback (it replaces the old manual drag-and-drop handoff;
  the approval gate still applies).
- Since pending review comments cannot be PATCHed, delete the pending review and recreate it with the image markup embedded in the comment bodies (same merge-guard and no-`event` rules as above).
- Verify after recreation: draft comment image counts via `--jq`, and that visible PR comments are unchanged (nothing leaked to the author).

## Appending to an existing pending review (GraphQL)

For net-new inline comments only; anchors follow the same `line`/`side` verification rules as the batch-create flow above.

```bash
# 1. Resolve the pending review's GraphQL node id (PRR_..., not the REST databaseId)
gh api graphql -f query='
query {
  repository(owner: "OWNER", name: "REPO") {
    pullRequest(number: NUM) {
      reviews(first: 10, states: PENDING) { nodes { id databaseId } }
    }
  }
}'

# 2. Append one thread per comment
BODY=$(cat /tmp/comment-body.md)
gh api graphql -f reviewId="PRR_xxx" -f body="$BODY" -f query='
mutation($reviewId: ID!, $body: String!) {
  addPullRequestReviewThread(input: {
    pullRequestReviewId: $reviewId,
    path: "path/to/file.ts", line: 42, side: RIGHT, body: $body
  }) { thread { id path line } }
}'
```

- `side` is an unquoted GraphQL enum (`RIGHT`/`LEFT`), unlike the REST string `"RIGHT"`.
- Pass bodies via `-f body="$VAR"` so a leading `@mention` is sent as text instead of treated as a file path.
- Gotcha: the review's `updatedAt` does not advance on append.
  Verify with `comments.totalCount` or per-comment `createdAt`, not `updatedAt`.

## After submitting, verify what actually posted

- The submitted review body is whatever you submit with the final event call.
  Show it in the approval payload before submission, even when the inline comments were already approved.
- For COMMENT/REQUEST_CHANGES, treat the body as required: always include the exact approved body.
- UI gotcha: switching the event type (e.g. Comment -> Approve) can drop the typed summary text in some flows.
  For API-based submission, prevent this by always sending the intended `body` with the submit request.
- Count posted inline comments and reconcile anything missing; if needed, post a follow-up (non-batch) comment with leftover deep links.

## Example: create a pending review with line/side anchoring (preferred)

```bash
cat > /tmp/review-payload.json <<'JSON'
{
  "commit_id": "HEAD_SHA",
  "body": "",
  "comments": [
    { "path": "path/to/file.ts", "line": 42, "side": "RIGHT", "body": "Comment text." },
    { "path": "path/to/file.ts", "line": 78, "side": "RIGHT", "body": "Another comment." }
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
# gh api repos/OWNER/REPO/pulls/NUM/reviews/REVIEW_ID/events -X POST -f event=APPROVE -f body=$'Looks good.'
```
