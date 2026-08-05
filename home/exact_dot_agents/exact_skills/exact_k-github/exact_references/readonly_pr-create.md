# GitHub PR Creation Reference

Load before `gh pr create` or PR body/title edits.

## PR creation rules

- Create PRs as draft by default.
- Resolve the referenced issue and whether it is `Closes #X` or `Addresses #X` from evidence first —
  branch name, commit messages, and PR context; ask only when that evidence leaves a genuine fork. Never invent issue numbers.
- If no existing issue exists, stop and ask whether to create one; do not create issues unless explicitly instructed.
- PR title is a human-readable change summary, not necessarily a Conventional Commit header.
- Multiline bodies/comments: use bash/zsh `$'...'` so `\n` becomes real newlines;
  do not rely on `\\n` escapes inside normal quotes with `gh api -f body=...`.
- Test Plan is inferred from the change surface; run the smallest sufficient checks and record commands/results.
- Repro-driven fixes need portable local repro steps plus commands/results; do not publish session-specific evidence such as private hostnames or browser automation state.
- Before creating/editing a PR body, ensure the Test Plan covers any `## Reproduction`, `Expected`, or `Actual` evidence from linked/closing issues.
  If manual repro was not run, include portable reviewer-run steps and say which automated checks ran.
- Always propose labels/assignees/milestone/projects first and get confirmation before applying metadata.

## Required publication packet

Before `gh pr create` or PR body/title edit, require the `k-compose-pr` PR publication packet.
Stop if the packet is missing, any required field is missing, or any required field is `blocked`.
Exempt: backport PRs opened by the `k-kbn-backport` tool flow — that skill's upfront publication approval gates them instead.

Packet requirements:

- UI-facing changes and linked screenshots/media: screenshot status and captured proof folder/filename mapping.
- PR templates: selected template and required-section checklist.
- Metadata: `approved_to_apply`, `applied`, `deferred`, or `pending_approval`.
- Do not treat `pending_approval` as no; surface it in approval or immediately after creation/readback.
- If screenshots are `explicitly_skipped`, the approval request must name that screenshots are skipped and cite explicit approval.

## Preflight ledger

Before the side effect, show:

- `target`: repo, base, head, draft/readiness
- `title`: exact title plus source/rationale
- `body`: body file/path or full text source, linked issue keyword, footer state
- `composition_packet`: template, screenshots, test plan, metadata, statuses, blockers
- `intake`: full linked issue/PR/comment bodies read; comments/replies status; skipped items with reasons
- `test_plan`: observable/manual steps, expected result, commands run, observed results
- `metadata`: proposed labels/assignees/milestone/projects plus source skill/rationale
- `approval`: exact side effect command/payload approved by the user

## Readback

After `gh pr create` or `gh pr edit`, read back title, body, labels, draft state, base/head, and closing keyword.
Compare each field against the approved preflight ledger; fix or get explicit acceptance for mismatches.
If metadata remained `pending_approval`, ask whether to apply now or defer. If approved, apply and read back metadata before completion.
