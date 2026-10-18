# GitHub PR Creation Reference

Load before `gh pr create` or PR body/title edits.

## PR creation rules

- Create PRs as draft by default.
- Keep PR reviewer fields unset; GitHub handles reviewer assignment automatically.
- Resolve the referenced issue and whether it is `Closes #X` or `Addresses #X` from evidence first —
  branch name, commit messages, and PR context; ask only when that evidence leaves a genuine fork. Use only verified issue numbers.
- If no existing issue exists, open the PR without an issue link; create issues only when explicitly instructed.
- PR title is a human-readable change summary, not necessarily a Conventional Commit header.
- Multiline bodies/comments: use bash/zsh `$'...'` so `\n` becomes real newlines;
  do not rely on `\\n` escapes inside normal quotes with `gh api -f body=...`.
- Test Plan content follows the `k-compose-pr` publication packet: reviewer-runnable steps plus the commands and observed results from the actual check runs.
- Repro-driven fixes need portable local repro steps plus commands/results; do not publish session-specific evidence such as private hostnames or browser automation state.
- Before creating/editing a PR body, ensure the Test Plan covers any `## Reproduction`, `Expected`, or `Actual` evidence from linked/closing issues.
  If manual repro was not run, include portable reviewer-run steps and say which automated checks ran.
- Never apply labels/assignees/milestone/projects without approval; list proposed metadata under `Proposed:` in the report, since a PR request does not name it.

## Required publication packet

Before `gh pr create` or PR body/title edit, require the `k-compose-pr` PR publication packet.
Stop if the packet is missing, any required field is missing, or any required field is `blocked`.

Approval handling:

- For `gh pr create` the user asked for, the request covers the title and body you draft from the packet (`~/AGENTS.md` §5).
  Show them first only when the user asked to see them.
- On a PR you opened in this task, a body/title edit that keeps it truthful needs no approval (`~/AGENTS.md` §5).
- For an existing PR body/title edit on any other PR, approval for the current PR workflow satisfies approval only when the packet proves the edit is required to complete, confirm, or keep truthful the approved sequence.
  This includes fix/test evidence from scoped commits or pushes already authorized in the same sequence.
- If the body/title has unresolved placeholders, or on a PR you did not open in this task has discretionary wording or changes it beyond the same requested update, draft the exact payload and wait for approval.
- This packet never authorizes unrelated metadata, reviewer replies/resolves, labels, invented prose, or a different target.

Packet requirements:

- UI-facing changes and linked screenshots/media: screenshot status; captured proof folder/filename mapping when `captured`.
- PR templates: selected template and required-section checklist.
- Metadata: `approved_to_apply`, `applied`, `deferred`, or `pending_approval`.
- Do not treat `pending_approval` as no; surface it in approval or immediately after creation/readback.
- If screenshots are `explicitly_skipped`, the report must name that screenshots are skipped and cite the user's words.

## Preflight ledger

Build this ledger before the side effect.
Show it to the user only when approval is needed (Approval handling above) or the user asked to see it:

- `target`: repo, base, head, draft/readiness
- `title`: exact title plus source/rationale
- `body`: body file/path or full text source, linked issue keyword, footer state
- `body_title_delta`: existing PR only; current read-back, exact replacement/delta, and evidence that the edit is required by the approved sequence
- `composition_packet`: template, screenshots, test plan, metadata, statuses, blockers
- `intake`: full linked issue/PR/comment bodies read; comments/replies status; skipped items with reasons
- `test_plan`: observable/manual steps, expected result, commands run, observed results
- `metadata`: proposed labels/assignees/milestone/projects plus source skill/rationale
- `approval`: the user request or approval that covers this side effect

## Readback

After `gh pr create` or `gh pr edit`, read back title, body, labels, draft state, base/head, and closing keyword.
Compare each field against the preflight ledger; fix mismatches.
If metadata remained `pending_approval`, list it under `Proposed:`; apply it only after the user approves it, then read it back.
