# Mode: PR Thread Replies (One Thread At A Time)

Precondition:

- You already loaded `~/.agents/playbooks/review/router.md`.
- Follow the router's shared rules.

Use when:

- the user asks to reply to reviewer comments
- the user asks to address/resolve review threads

Out of scope:

- If the user wants to apply code changes while processing threads (and run lint/type_check/tests per cycle),
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
2A. Verify you are addressing the exact concern/line.
   - If the reviewer comment is anchored to a specific line/guard, ensure your reply (or links you provide)
      directly addresses that exact line. Avoid replying with adjacent-but-not-relevant tests/behavior.
    - If you realize the thread is about adding a code comment/documentation, do not try to "explain it away"
      in the PR reply. Switch to PR change-cycle and make the comment in code, then reply with a commit link.
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

- Do not use `RE:` headers/prefixes.
- Default: reply directly (no quoting) when you're responding to the entire comment.
- If you must reference a specific fragment, quote only the minimum needed using a Markdown blockquote (`> ...`), then reply.
- Avoid email-style quote/reply interleaving.
- Keep it short; prefer a concrete change suggestion.
- If a thread is obsolete because later commits superseded the hunk, prefer a single-line reply:
  - `Superseded by <commit link>` (optionally add one link to the new canonical thread).

Output (one reply per turn):

- `Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<base>...HEAD`
  - reviewer metadata only; do not include in GitHub comment bodies
- Where it goes (comment id / file thread)
- Reply body (end with `Wdyt`)
- Resolution recommendation: `resolve` | `keep_open`
