# Mode: PR Review Start (Batch Draft)

Precondition:

- You already loaded `~/.agents/playbooks/review/router.md`.
- Follow the router's shared rules.

Use when:

- the user wants an initial full PR review drafted in one go
- the user provides a PR URL/number without asking for reply-only or
  one-at-a-time

Out of scope:

- If the user wants to apply requested changes while processing review feedback (one thread/comment at a time),
  use `~/.agents/playbooks/review/pr_change_cycle.md` instead.

## PR Common Setup (All PR Modes)

Resolve the PR target (avoid searching):

- If the user provided a PR URL/number, use that.
- Otherwise:
  - Set `GH_PAGER=cat` for all `gh` calls (prevents interactive pager hangs).
  - Resolve PR number via `,gh-prw`:
    - `,gh-prw --number`
  - If `,gh-prw` fails once, stop and ask the user for the PR URL/number.

Media evidence:

- Treat screenshots/GIFs/videos as first-class evidence:
  - open every inline image/attachment in the PR description and comment threads
  - if a claim depends on visuals and visuals are missing/unclear, ask for
    visuals

Base-branch context gate (mandatory):

- You must compare the PR against how base works today.

Preflight (blocking):

- Run `list_indices` first (try both `scsi-main` and `scsi-local`).
- If the user provided an index name:
  - verify it exists in `list_indices`
  - if it does not exist, stop and ask which index to use
- If the user did not provide an index name:
  - select an index only if you can justify it from evidence; otherwise ask the user
    which index represents the base branch for this repo

Base context sources:

- Preferred: semantic code search (when available):
  - Follow: `~/.agents/playbooks/code_search/semantic_code_search.md`
  - Invoke at least one SCSI tool to establish base behavior/invariants.
- Fallback: local base context:
  - `rg` + file reads
  - `git show <base>:<path>`
  - `git diff <base>...HEAD`

Local verification:

- Run the smallest sufficient tests.
- If the concern is behavioral, reproduce/simulate it in `/tmp` or the worktree.
- UI repro hygiene (when verifying UI/editor behavior):
  - do one claim per repro run; reset state between runs (reload/new tab)
  - clear inputs deterministically before typing
  - for rich editors, do not assume the accessible textarea reflects the full
    editor model; verify what is actually rendered

Comment placement (draft guidance):

Where to comment:

- Default: inline on a relevant diff line/range in the PR.
- File-scoped concerns: prefer a file-level comment (`subject_type=file`).
- If you are replying in an existing thread, use PR thread replies mode.

Anchoring constraints (only if posting is requested):

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
  - anchor on the nearest relevant diff line in the same file and include a
    deep link to the exact source location on the PR head SHA
- If you cannot find a relevant diff anchor without confusing the author:
  - use a file-level comment (`subject_type=file`)
  - or a PR-level comment that links to the exact source lines

Deep links to exact source lines (PR head SHA):

- Prefer links of the form:
  `https://github.com/OWNER/REPO/blob/<head_sha>/<path>#L<start>-L<end>`
- If you cannot reliably compute line numbers from GitHub, fetch the PR head
  commit locally and use `git show <head_sha>:<path>` to compute them.

If posting is requested:

- Follow `~/.agents/playbooks/github/gh_workflow.md` for exact anchoring and API
  constraints.

Complete pass before drafting (do not skip):

- PR description + all links (follow recursively until nothing left to
  investigate)
- all review threads/replies (end-to-end)
- full diff
- referenced screenshots/GIFs/videos
- targeted local verification for risky claims

Review contract:

- Build a complete internal findings queue ordered by severity.
- Draft highest-risk items first.

Output:

- Return a batch `Pending review draft` containing:
  - `Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<base>...HEAD`
    - reviewer metadata only; do not include in GitHub comment bodies
  - `inline_comments`: one draft per finding worth commenting, each with:
    - Where (file path + line/range when possible)
    - Comment body (end with `Wdyt`)
    - Why it matters (1-2 lines)
    - How to verify (minimal)
    - Proposed fix (smallest change)
  - `summary_comment` (optional): short PR-level comment (end with `Wdyt`)

Draft persistence:

- If the user says "consult before sending", keep the full batch draft in a
  single scratch file under `/tmp/` so it can be reviewed/edited before
  posting. Do not post until explicitly asked.
