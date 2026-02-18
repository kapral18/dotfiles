# Mode: PR Review Iterative (One New Comment At A Time)

Precondition:

- You already loaded `~/.agents/playbooks/review/router.md`.
- Follow the router's shared rules.

Use when:

- the user asks "what's the next comment"
- the user says "continue the review"
- the user wants "one comment at a time"

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

- If the user did not provide an index name, run `list_indices` now (try both
  `scsi-main` and `scsi-local`) to determine whether the repo is indexed.

If the repo is indexed:

- Semantic code search is required for base context:
  - Follow: `~/.agents/playbooks/code_search/semantic_code_search.md`
  - Select and record the index.
  - Invoke at least one SCSI tool to establish base behavior/invariants.

If semantic tools are unavailable or the repo is not indexed:

- Use local base context:
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

Context before drafting:

- On the first turn of an iterative PR session, do a complete pass before
  drafting:
  - PR description + linked issues/PRs/docs (follow until nothing left to open)
  - all review threads/replies (end-to-end)
  - full diff
  - referenced screenshots/GIFs/videos
  - targeted local verification for risky claims
- On later turns, keep working from the internal findings queue (do not re-read
  everything unless needed).

Review contract:

- Maintain a full internal findings queue ordered by severity.
- Each turn: draft exactly one new review comment for the highest-priority
  unresolved finding, then stop.

Output (exactly one finding per turn):

- `Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<base>...HEAD`
  - reviewer metadata only; do not include in GitHub comment bodies
- Where (file path + line/range when possible)
- What's wrong (concrete)
- Why it matters (impact)
- How to verify (minimal repro/test)
- Proposed fix (smallest change)
- End with `Wdyt`.

If you need to reply to an existing review thread:

- Use PR thread replies mode instead of mixing reply drafting into this mode.
