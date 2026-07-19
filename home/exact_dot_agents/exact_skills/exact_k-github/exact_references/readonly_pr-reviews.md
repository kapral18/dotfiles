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
> **Pre-flight checklist (mandatory before every review POST):**
>
> 1. Read back the JSON payload you are about to send.
> 2. Confirm the `event` key is **absent** from the payload.
> 3. If `event` is present, **remove it** before sending.
> 4. Only add `event` in a **separate** submit call after the user explicitly
>    asks to publish.
> 5. For code-review feedback, default to inline anchored `comments[]` (not body-only summary),
>    unless the user explicitly asks for PR-level summary feedback.
> 6. In `body` and each inline comment body,
>    any code/file/symbol reference must be a clickable source link (exact file + line/range on PR head SHA), not plain text.
> 7. Fetch the current PR diff/patch for the target head SHA and verify every `line`/`side`, range, or
>    `position` anchor is inside the intended diff hunk immediately before creating or submitting the review.
>    Do not rely on full-file line numbers, stale patches, or memory.
> 8. Read existing current-account pending reviews and reconcile them with the payload. Do not create or submit fragmented review feedback.
> 9. For UI-related review feedback drafted after `/k-agent-review` or `live-ui-review`, verify the approved draft includes `ui_evidence_attachments` or a valid blocker/non-applicability reason.
>    Keep local screenshot paths out of `body` and inline comment bodies; show the handoff separately in the approval payload.

- Definition: a "pending review" is a PR review whose API `state` is `PENDING`.
  It is visible only to the reviewer who created it until submission (COMMENT/APPROVE/REQUEST_CHANGES), and it does not appear to the PR author as posted review comments while pending.
- Creating a PENDING (draft) PR review requires the reviews API. Omit `event` in: `POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews`
- Batch draft comments: include all inline review comments in the `comments` array in that same request.
- Practical constraint: GitHub generally allows only one `PENDING` review per user per PR.
  If you need to change bodies/anchors, delete the pending review and recreate it.
- Pending inline review comments are not practically editable via API; do not waste time trying to PATCH.
  Delete the pending review and recreate it with the corrected payload.
- Do not try to attach comments to an already-created pending review via the PR comments endpoint (it won't accept `pull_request_review_id`).
  If you need to change anchors/bodies, delete the pending review and recreate it.
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
  4. Compare the pending review body/comments against the approved draft from `k-review`/`k-agent-review` and its `Pending review reconciliation:` ledger.
  5. If any approved review feedback is UI-related and drafted after `/k-agent-review` or `live-ui-review`, compare it against the draft's `ui_evidence_attachments` ledger and block if screenshot evidence is missing without a valid blocker/non-applicability reason.
- If no reconciliation ledger exists, run the review skill's Existing Pending Review Reconciliation before mutating GitHub.
- If a pending review exists and the new payload is additive/replacement:
  - do not try to create a second pending review
  - prepare one consolidated payload that keeps still-valid pending findings and adds net-new findings exactly once
  - show the exact old pending review ID, comments to keep/drop, new payload, and delete/recreate action; wait for explicit approval
- If submitting an existing pending review:
  - fetch the pending review and comments immediately before the submit call
  - verify they match the approved reconciled payload and current head anchors
  - if they differ, stop and ask for approval to replace/reconcile first
- If a pending review contains stale or contradictory feedback, do not submit it.
  Delete/recreate only after explicit approval with the consolidated replacement payload.

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
- Keep the review summary body empty unless the user explicitly wants a public summary.

## Embedding screenshot images in review comments

Upload mechanics, URL harvesting, and image/video layout rules are generic and live in `~/.agents/skills/k-github/references/attachments.md` — load that reference first.
Review-specific rules on top of it:

- Use this flow when the user approves attaching local screenshots to review feedback (it replaces the old manual drag-and-drop handoff;
  the approval gate still applies).
- Since pending review comments cannot be PATCHed, delete the pending review and recreate it with the image markup embedded in the comment bodies (same merge-guard and no-`event` rules as above).
- Verify after recreation: draft comment image counts via `--jq`, and that visible PR comments are unchanged (nothing leaked to the author).

## After submitting, verify what actually posted

- The submitted review body is whatever you submit with the final event call.
  If you want a summary, include it explicitly when submitting (COMMENT/APPROVE/REQUEST_CHANGES).
- For COMMENT/REQUEST_CHANGES, treat the body as required: always include it.
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
