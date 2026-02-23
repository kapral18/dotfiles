# Mode: PR Change Cycle (Apply Reviewer Feedback With Verification)

Precondition:

- You already loaded `~/.agents/playbooks/review/router.md`.
- Follow the router's shared rules (especially base-branch context + truth validation).

Use when:

- the user wants to apply requested PR changes from review comments
- the user wants to go one thread/comment at a time and decide together what to do
- the user wants experiments + lint/type_check/tests after each iteration cycle

## PR Common Setup

Resolve the PR target (avoid searching):

- If the user provided a PR URL/number, use that.
- Otherwise:
  - Set `GH_PAGER=cat` for all `gh` calls (prevents interactive pager hangs).
  - Resolve PR number via `,gh-prw`:
    - `,gh-prw --number`
  - If `,gh-prw` fails once, stop and ask the user for the PR URL/number.

Context intake (first turn only):

- Read:
  - PR description + linked issues/PRs/docs
  - all review threads (end-to-end)
  - full diff
  - referenced screenshots/GIFs/videos

Base-branch context gate (mandatory):

- Run `list_indices` first (try both `scsi-main` and `scsi-local`).
- If the user provided an index name:
  - verify it exists in `list_indices`
  - if it does not exist, stop and ask which index to use
- If the user did not provide an index name:
  - select an index only if you can justify it from evidence; otherwise ask the user
    which index represents the base branch for this repo
- Preferred: semantic code search (when available):
  - Follow: `~/.agents/playbooks/code_search/semantic_code_search.md`
  - Invoke at least one SCSI tool to establish base behavior/invariants for the area under review.
- Fallback: local base context:
  - `rg` + file reads
  - `git show <base>:<path>`
  - `git diff <base>...HEAD`

## One Thread/Comment Per Turn (Do Not Skip)

Iteration contract:

- Pick exactly one reviewer thread/comment.
- Do not move to the next thread/comment until you and the user agree on what to do.

Per-thread workflow:

1. Identify the next active reviewer request:
   - unresolved threads
   - requested-changes style comments
   - or the highest-risk comment if there is no explicit ordering

2. Read the entire thread end-to-end.

3. Restate the concern as a falsifiable hypothesis:
   - what the reviewer believes is wrong
   - what correct behavior/invariant should be
   - what would prove/disprove it

4. Establish base context for this exact concern:
   - use SCSI (when indexed) to learn how base currently does it
   - extract 1-3 concrete base invariants (types, call sites, ownership boundaries, runtime expectations)

5. Self-critique your current diff:
   - why your change originally made sense
   - which invariant(s) it was optimizing for
   - where it might be overfitting or making types worse downstream

6. Choose an approach (one):
   - accept and implement the smallest safe change
   - reject/clarify with evidence (base context + repro)
   - ask exactly one blocking question (include the default assumption)

6A. Scope guardrail (reduce review noise):
   - If the reviewer request is a "clarity" ask (add comment, rename, tiny refactor), prefer the smallest
     localized change that satisfies the request.
   - If the reviewer request is out-of-scope cleanup, you may treat it as a "graceful gesture" only when:
     - it is cheap
     - it does not change runtime behavior
     - it reduces future confusion
     Otherwise: reply proposing a follow-up (do not expand the change-set).

7. Experiment and verify assumptions:
   - Prefer the smallest reproduction in `/tmp` when possible.
   - If the change needs integration context, apply a minimal patch in the worktree.
   - For type changes: validate the full type chain (call sites + inference + exported types), not just the edited file.

8. Quality gates (required after each code-change iteration cycle):
   - Run lint + type_check + tests.
   - Discover the correct commands from the repo (do not guess):
     - check `package.json` scripts (or equivalent build tooling) for `lint`, `typecheck`, `test`
     - if monorepo, prefer scoped/targeted commands for the affected package first
     - if you cannot determine the commands from repo sources, stop and ask the user

9. Re-evaluate:
   - If checks fail or types get worse, back out or adjust and repeat steps 6-8.
   - If checks pass, draft the reply for that thread (and only that thread).
     - If the thread asked for code comments/documentation: make the change in code, then reply with a short
        "Fixed in <commit link>" message (avoid long explanations in the thread).
     - If your fix ended up elsewhere (different file/thread): reply with a link to the canonical thread/commit
       rather than re-explaining, to avoid duplicated discussion.

## Output (Exactly One Thread/Comment Per Turn)

- `Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<base>...HEAD`
  - reviewer metadata only; do not include in GitHub comment bodies
- Thread reference (comment id / file thread)
- Hypothesis (1-2 lines)
- Evidence:
  - base invariant(s) (what base does)
  - experiment result(s) (what you observed)
- Proposed change (or decision to push back / ask a question)
- Verification run:
  - lint / type_check / tests (what you ran)
  - pass/fail and the key error signal if failed
- Draft reply body (end with `Wdyt`)
- Recommendation: `resolve` | `keep_open`

Boundaries:

- Do not commit/push unless explicitly asked.
- Do not post to GitHub or resolve threads unless explicitly asked.
