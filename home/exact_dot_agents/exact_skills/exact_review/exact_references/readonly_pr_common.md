# PR Common Setup

All PR review modes load this file. Do not duplicate these rules in mode files.

## Resolve the PR Target (Avoid Searching)

- If the user provided a PR URL/number, use that.
- Otherwise:
  - Set `GH_PAGER=cat` for all `gh` calls (prevents interactive pager hangs).
  - Resolve PR number via `,gh-prw`:
    - `,gh-prw --number`
  - If `,gh-prw` fails once, stop and ask the user for the PR URL/number.

## Media Evidence

- Treat screenshots/GIFs/videos as first-class evidence:
  - open every inline image/attachment in the PR description and comment threads
  - if a claim depends on visuals and visuals are missing/unclear, ask for
    visuals

## Comment Placement (Draft Guidance)

Where to comment:

- Default: inline on a relevant diff line/range in the PR.
- File-scoped concerns: prefer a file-level comment (`subject_type=file`).
- If you are replying in an existing thread, use the reply mode of PR fix.

## Anchoring Constraints (Only If Posting Is Requested)

- PR review comments are anchored to the PR's unified diff. The GitHub UI can
  sometimes let you comment on context lines by expanding the diff, but API
  calls still need a resolvable diff anchor.
- For API calls, do not assume a source-file line number is a valid anchor.
  Prefer:
  - `position` (diff-relative), computed from the PR's unified diff:
    - 1-based count of lines starting at the first `@@` hunk header in that file
    - continues across subsequent hunks until the next file
  - or `line` + `side` / `start_line` + `start_side` (still must resolve against
    the PR diff; GitHub will 422 if it cannot resolve)
- If the specific source line you care about is not shown in the diff context:
  - do NOT anchor the comment to an unrelated line
  - anchor on the nearest relevant diff line in the same file and include a deep
    link to the exact source location on the PR head SHA
- If you cannot find a relevant diff anchor without confusing the author:
  - use a file-level comment (`subject_type=file`)
  - or a PR-level comment that links to the exact source lines

## Deep Links to Exact Source Lines (PR Head SHA)

- Prefer links of the form:
  `https://github.com/OWNER/REPO/blob/<head_sha>/<path>#L<start>-L<end>`
- If you cannot reliably compute line numbers from GitHub, fetch the PR head
  commit locally and use `git show <head_sha>:<path>` to compute them.

## Local Verification

- Run the smallest sufficient tests.
- If the concern is behavioral, reproduce/simulate it in `/tmp` or the worktree.
- UI repro hygiene (when verifying UI/editor behavior):
  - do one claim per repro run; reset state between runs (reload/new tab)
  - clear inputs deterministically before typing
  - for rich editors, do not assume the accessible textarea reflects the full
    editor model; verify what is actually rendered

## If Posting Is Requested

- Follow `~/.agents/skills/github/SKILL.md` for exact anchoring and API
  constraints.
