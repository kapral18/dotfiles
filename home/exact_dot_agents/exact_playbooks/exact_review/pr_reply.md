# Mode: PR Thread Replies (One Thread At A Time)

Precondition:

- You already loaded `~/.agents/playbooks/review/router.md`.
- Follow the router's shared rules.

Use when:

- the user asks to reply to reviewer comments
- the user asks to address/resolve review threads

## PR Common Setup (All PR Modes)

Resolve the PR target (avoid searching):

- If the user provided a PR URL/number, use that.
- Otherwise:
  - Set `GH_PAGER=cat` for all `gh` calls (prevents interactive pager hangs).
  - Resolve PR number via `gh prw`:
    - `GH_PAGER=cat gh prw --number`
  - If `gh prw` fails once, stop and ask the user for the PR URL/number.

Media evidence:

- Treat screenshots/GIFs/videos as first-class evidence:
  - open every inline image/attachment in the PR description and comment threads
  - if a claim depends on visuals and visuals are missing/unclear, ask for
    visuals

Optional context pull (base branch patterns):

- Use semantic code search primarily to learn base-branch context, then compare
  against the PR branch changes:
  - `~/.agents/playbooks/code_search/semantic_code_search.md`
- If semantic tools are unavailable or the repo is not indexed, use local search
  (`rg` + file reads) to build equivalent context.
- If needed, cross-check base-branch source with git:
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

- If you are replying in an existing thread, reply in that thread (do not create
  a new top-level comment).
- If you need to reference exact source lines, include a deep link to the PR
  head SHA.

Deep links to exact source lines (PR head SHA):

- Prefer links of the form:
  `https://github.com/OWNER/REPO/blob/<head_sha>/<path>#L<start>-L<end>`
- If you cannot reliably compute line numbers from GitHub, fetch the PR head
  commit locally and use `git show <head_sha>:<path>` to compute them.

If posting is requested:

- Follow `~/.agents/playbooks/github/gh_workflow.md` for exact anchoring and API
  constraints.

Thread workflow (repeat per thread):

1. Identify the next active thread (unresolved / awaiting reply).
2. Read the entire thread end-to-end before replying (including earlier
   context).
3. Restate the concern in one sentence.
4. Choose response type:
   - accept + propose the smallest fix
   - clarify a misunderstanding with evidence
   - ask exactly one blocking question (include the default assumption)
5. Draft one reply.
6. Recommend resolution:
   - `resolve` only when addressed and no follow-up is needed
   - otherwise `keep_open`

Reply style rules:

- No quote replies inside threads.
- Keep it short; prefer a concrete change suggestion.

Output (one reply per turn):

- Where it goes (comment id / file thread)
- Reply body (end with `Wdyt`)
- Resolution recommendation: `resolve` | `keep_open`
