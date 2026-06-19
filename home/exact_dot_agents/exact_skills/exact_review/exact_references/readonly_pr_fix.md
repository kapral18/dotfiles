# Mode: PR Fix (Address Reviewer Feedback)

Precondition:

- You already loaded `~/.agents/skills/review/SKILL.md`.
- Follow `~/.agents/skills/review/references/judging_core.md` and `~/.agents/skills/review/references/shared_rules.md` (loaded once by the router; do not re-load).
- Follow `~/.agents/skills/review/references/pr_common.md` for PR setup, media evidence, comment placement, anchoring, deep links, and local verification.

Use when:

- the user asks to reply to reviewer comments or address review threads
- the user wants to apply requested PR changes from review feedback
- the user wants to go one thread/comment at a time and decide together what to do

Out of scope:

- If the user wants to review a PR (draft new review comments, not address existing ones), use `~/.agents/skills/review/references/pr_review.md` instead.

## Authorship Note

PR fix edits code, so resolve `authorship` via the router's Role Detection / Authorship section.

This mode may edit only when:

- the user owns the PR
- or the user explicitly asked to apply/fix changes on that PR

Explicit fix requests include:

- "fix these"
- "take over this branch"

If `authorship` is `other`/`unknown` and no explicit fix request exists:

- do not edit
- fall back to draft-only PR review (`pr_review.md`)
- confirm intent

## Context Intake (First Turn Only)

- Read:
  - complete the GitHub Context Intake + Reference Resolution gate in pr_common.md
  - treat that gate as blocking
  - resolve before proceeding:
    - full descriptions/bodies
    - comments
    - replies
    - threads
    - media
    - recursive references
  - run Ambient Topic Exploration in pr_common.md when disagreement, unclear shared understanding, or missing topic history matters
  - run Existing Pending Review Reconciliation in pr_common.md before drafting any new review feedback or publishing/submitting review content
  - all review threads (end-to-end)
  - full diff

## Base-Branch Context

Follow the base-branch context gate in `shared_rules.md`. This is mandatory.

## One Thread/Comment Per Turn (Do Not Skip)

Iteration contract:

- Pick exactly one reviewer thread/comment.
- Do not move to the next thread/comment until you and the user agree on what to do.
- Exception: switch to Drain Mode when the user explicitly asks to batch.
- Batch/repeat phrases include:
  - "repeat the process"
  - "same procedure"
  - "you know the drill"
  - "address all"
  - "no time constraints"
  - "drain"

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
   - Before drafting, compare the reply/fix note with any current-account pending review, submitted review comment, or prior reply discovered by Existing Pending Review Reconciliation.
   - If the same point is already pending, merge the reply intent into the pending-review replacement plan instead of creating a competing comment.
   - If prior current-account content is stale or contradicted by current head, draft one correction/replacement path; do not publish both versions.
   - If the thread asked for code comments/documentation:
     - make the change in code
     - reply with a short `Fixed in <commit URL>` message
     - avoid long explanations in the thread
     - use full clickable GitHub URLs for commits
     - never use bare hashes
   - If your fix ended up elsewhere (different file/thread): reply with a clickable link to the canonical commit/thread rather than re-explaining.

### Reply Style

Reply tone and triage patterns are centralized in `~/.agents/skills/communication/SKILL.md`.

Follow it for:

- concision
- thanks + resolve
- reopen + ask what's blocking

Review-specific mechanics only:

- Verify the outcome against the current head before replying/resolving (the author's claim is not proof).
- If the thread asked for a code/doc change you made: reply `Fixed in <full commit URL>` (avoid long explanations in-thread).
- If a thread is obsolete because later commits superseded the hunk: `Superseded by <commit link>` (optionally one link to the new canonical thread).
- Resolve/unresolve and any reply to a human author stay gated:
  - draft first
  - show the exact payload + target
  - wait for approval
  - follow Posting Boundary in `shared_rules.md`
  - follow Human-Visible Publication Gate in `~/AGENTS.md`

## Drain Mode (Batch, Explicitly Invoked)

Use Drain Mode only when the user explicitly asks to batch/repeat.

In Drain Mode:

- run the per-thread workflow back-to-back
- continue until no unresolved actionable thread remains
- do not re-ask "what next?" for each thread
- do not relax the Human-Visible Publication Gate (SOP, `~/AGENTS.md`)

Author-type classification (do first, per thread, verified — not guessed):

- `gh api repos/OWNER/REPO/pulls/comments/COMMENT_ID --jq '{login:.user.login, type:.user.type, assoc:.author_association}'`
- Bot = `user.type == "Bot"` OR login ends with `[bot]` OR login in the known-bot allowlist (`elasticmachine`, `kibanamachine`, `github-actions[bot]`).
- Ambiguous/unknown author, or a thread with both human and bot participants -> treat as human.

Per-thread branch:

- **Bot-authored thread:**
  - run the full Per-Thread Workflow
  - include state-machine verification when applicable
  - auto-reply with `Fixed in <commit URL>` or evidence
  - auto-resolve
  - continue to the next thread without stopping
- **Human-authored thread:**
  - run the same workflow
  - make any code fix in the working tree
  - stop before publishing
  - queue the drafted reply + resolve recommendation
  - surface it for supervision
  - do not post or resolve
  - continue investigating/queuing remaining threads
  - never publish a human-visible reply/resolve without explicit approval

Loop control:

- Commit/push still require explicit approval (git skill) regardless of mode; Drain Mode never auto-commits or auto-pushes.
- After each thread, append the decision to the review persistence spec (see shared_rules.md) so the loop is resumable after pruning.
- End condition:
  - no unresolved actionable threads remain
  - or only human-thread drafts await approval
- Report:
  - bot threads auto-resolved
  - human drafts pending approval
  - validation run
  - remaining open items

## Output (One Thread Per Turn)

- `Base context:` line (see shared_rules.md)
- `Pending review reconciliation:` line when current-account pending/submitted review content affects the thread response
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

## Post-Review Stage (After Code Fixes, Before Completing)

After this session's code fixes are made and quality gates are green, run the Post-Review Stage in `judging_core.md`.

Use the **fix diff** as the subject:

- a single thread's fix
- or the full set across a Drain Mode batch
- `git diff`
- or the commit range/staged set for this session

Do not use the original PR diff as the subject.

- Apply the four dimensions (redundancy, verbosity, semantic + logical duplication, gaps) to that fix diff.
- Resolve each hygiene finding in the working tree (this is your own PR's code) and re-run quality gates if the post-review fixes touched code.
- This is distinct from "verify the outcome against current head" (step 9): that confirms the fix _works_; this confirms the fix is _clean_.
- If no code was changed this session (reply-only threads), skip this stage.

## Boundaries

- Do not commit/push unless explicitly asked.
- Do not post to GitHub or resolve threads unless explicitly asked.
- Exception: verified bot-authored threads inside an explicitly-invoked Drain Mode flow (SOP, `~/AGENTS.md`).
- Human-visible replies/resolves are always supervised.
- Ambiguous/mixed threads fail safe to human.
