# Mode: PR Fix (Address Reviewer Feedback)

Precondition:

- You already loaded `~/.agents/skills/review/SKILL.md`.
- Follow `~/.agents/skills/review/references/shared_rules.md` (loaded once by the router; do not re-load).
- Follow `~/.agents/skills/review/references/pr_common.md` for PR setup, media evidence, comment placement, anchoring, deep links, and local verification.

Use when:

- the user asks to reply to reviewer comments or address review threads
- the user wants to apply requested PR changes from review feedback
- the user wants to go one thread/comment at a time and decide together what to do

Out of scope:

- If the user wants to review a PR (draft new review comments, not address existing ones), use `~/.agents/skills/review/references/pr_review.md` instead.

## Context Intake (First Turn Only)

- Read:
  - complete the Reference Resolution gate in pr_common.md (blocking — all links, media, and recursive references must be resolved before proceeding)
  - all review threads (end-to-end)
  - full diff

## Base-Branch Context

Follow the base-branch context gate in `shared_rules.md`. This is mandatory.

## One Thread/Comment Per Turn (Do Not Skip)

Iteration contract:

- Pick exactly one reviewer thread/comment.
- Do not move to the next thread/comment until you and the user agree on what to do.

### Per-Thread Workflow

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

6. Choose a response type (one per thread):

   **Reply-only** (no code change needed):
   - clarify a misunderstanding with evidence
   - explain the design decision with base-context anchoring
   - agree + propose a follow-up issue for out-of-scope work

   **Code change** (the reviewer's concern requires a fix):
   - accept and implement the smallest safe change
   - experiment and verify (prefer `/tmp` reproduction; if integration context needed, apply minimal patch in worktree)
   - for type changes: validate the full type chain (call sites + inference + exported types), not just the edited file

   **Ask** (blocking ambiguity):
   - ask exactly one blocking question (include the default assumption)

7. Scope guardrail (reduce review noise):
   - If the reviewer request is a "clarity" ask (add comment, rename, tiny refactor), prefer the smallest localized change that satisfies the request.
   - If the reviewer request is out-of-scope cleanup, you may treat it as a "graceful gesture" only when:
     - it is cheap
     - it does not change runtime behavior
     - it reduces future confusion
   - Otherwise: reply proposing a follow-up (do not expand the change-set).

8. If you chose code change — quality gates (required after each change):
   - Run lint + type_check + tests.
   - Discover the correct commands from the repo (do not guess):
     - check `package.json` scripts (or equivalent build tooling) for `lint`, `typecheck`, `test`
     - if monorepo, prefer scoped/targeted commands for the affected package first
     - if you cannot determine the commands from repo sources, stop and ask the user
   - If checks fail or types get worse, back out or adjust and repeat.

9. Draft the reply for that thread (and only that thread).
   - If the thread asked for code comments/documentation: make the change in code, then reply with a short "Fixed in `<commit URL>`" message (avoid long explanations in the thread). See Draft Style in shared_rules.md — commit references must be full clickable GitHub URLs, never bare hashes.
   - If your fix ended up elsewhere (different file/thread): reply with a clickable link to the canonical commit/thread rather than re-explaining.

### Reply Style

- Do not use `RE:` headers/prefixes.
- Default: reply directly (no quoting) when responding to the entire comment.
- If you must reference a specific fragment, quote only the minimum needed using a Markdown blockquote (`> ...`), then reply.
- Avoid email-style quote/reply interleaving.
- Keep it short; prefer a concrete change suggestion.
- If a thread is obsolete because later commits superseded the hunk, prefer a single-line reply:
  - `Superseded by <commit link>` (optionally add one link to the new canonical thread).

## Output (One Thread Per Turn)

- `Base context:` line (see shared_rules.md)
- Thread reference (comment id / file thread)
- Hypothesis (1-2 lines)
- Evidence:
  - base invariant(s) (what base does)
  - experiment result(s) (what you observed)
- Response type: `reply-only` | `code-change` | `ask`
- If code change:
  - proposed change
  - verification run: lint / type_check / tests (what you ran, pass/fail, key error signal if failed)
- Draft reply body
- Recommendation: `resolve` | `keep_open`

## Boundaries

- Do not commit/push unless explicitly asked.
- Do not post to GitHub or resolve threads unless explicitly asked.
