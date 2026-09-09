# Mode: PR Review

Precondition:

- You already loaded `~/.agents/skills/k-review/SKILL.md`.
- Follow `~/.agents/skills/k-review/references/judging_core.md` and `~/.agents/skills/k-review/references/shared_rules.md` (loaded once by the router; do not re-load).
- Follow `~/.agents/skills/k-review/references/pr_common.md` for PR setup, media evidence, comment placement, anchoring, deep links, and local verification.

Use when:

- the user wants a PR review (initial or continued)
- the user provides a PR URL/number and says "review"
- the user asks to recheck/verify whether a PR fix resolves a bug
- example phrases:
  - "does this PR fix it"
  - "can you recheck"
  - "verify this fix"
  - "check my comment"
  - "is it resolved on the updated branch"
- the user says "what's the next comment", "continue the review", or wants "one comment at a time"

Out of scope:

- If the user wants to apply requested changes from reviewer feedback (code changes + replies per thread), use `~/.agents/skills/k-review/references/pr_fix.md` instead.

## Role-Dependent Behavior

Resolve authorship through the router.
Review remains read-only for self, other, and unknown authorship unless the user explicitly requested fixes.
For other/unknown authorship, establish PR intent/necessity in Understand using applicable `~/.agents/skills/k-review/references/pr_context_audits.md` questions.
Known authorized fixes belong to Produce before one final review; new final findings are reported without automatic edits.

## Complete Pass Before Drafting (Mandatory)

On the first turn (or when starting a fresh review):

- complete the GitHub Context Intake + Reference Resolution gate in ~/.agents/skills/k-review/references/pr_common.md
- treat that gate as blocking
- resolve before proceeding:
  - full descriptions/bodies
  - comments
  - replies
  - threads
  - media
  - references needed to settle the named material questions
- run Ambient Topic Exploration in ~/.agents/skills/k-review/references/pr_context_audits.md when disagreement, unclear shared understanding, or missing topic history matters
- run the PR Necessity + Correctly-Open Audit in ~/.agents/skills/k-review/references/pr_context_audits.md when reviewing someone else's PR or when authorship is unknown
- run Existing Pending Review Reconciliation in ~/.agents/skills/k-review/references/pr_common.md before producing the final review draft
- all review threads/replies (end-to-end)
- full diff, scoped and read per ~/.agents/skills/k-review/references/pr_snapshot.md, and enclosing files (never review diff hunks in isolation; inspect surrounding callers and sibling consumers)
- historical provenance: in large repos, run targeted line-bounded probes (`git blame -L <start>,<end>` / `git log -n 5 -L`) on modified existing logic to understand why it was built and ensure past bug fixes are preserved
- targeted local verification for risky claims (see ~/.agents/skills/k-review/references/pr_common.md)

On later turns (iterative/continued):

- keep working from the internal findings queue
- do not re-read everything unless needed
- run the Drift check first (head and discussion, ~/.agents/skills/k-review/references/pr_snapshot.md);
  only the artifacts it reports as changed go through the intake gate again before relying on the prior queue
- a new comment, link, or reference surfaces through that Drift diff, not through recall; run the intake gate for exactly those artifacts

## Base-Branch Context

Follow the base-branch context gate in `~/.agents/skills/k-review/references/shared_rules.md`. This is mandatory.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Preserve requested review and adversarial lenses; deep or high-risk work needs distinct artifact-review and challenge questions in the same final stage.
Pass the actual frozen diff, context pointers, selected criteria, and complete existing check receipts.
Do not add a findings-audit, post-review, or reviewer-of-reviewer lane. Use blind fresh-eyes only for concrete comprehension risk.
Run required UI evidence in the same final stage with a verified target. Reconcile pending review content before delivery.
Record active/terminal packet IDs and never relaunch or wake completed workers.

## Output Mode

### Batch (default)

Return a `Pending review draft` containing:

- `Base context:` line (see ~/.agents/skills/k-review/references/shared_rules.md)
- `Pending review reconciliation:` line (see ~/.agents/skills/k-review/references/pr_common.md)
- `review_submission`: the exact submit `event` recommendation and PR-level review `body`;
  keep the body as a short acknowledgement (for example, `Looks good.` for a clean approval, or `Left inline feedback.` when comments exist) and include it in any posting approval payload.
  Do not repeat, summarize, or enumerate details that are already in inline comments.
- `inline_comments`: one draft per finding worth commenting, each with:
  - Where (file path + line/range when possible)
  - Comment body
  - Why it matters (1-2 lines)
  - How to verify (minimal)
  - Proposed fix (smallest change)
- `ui_evidence_attachments`: for UI-related findings drafted after `/k-deep-review` or `k-agent-live-ui-review`, screenshot handoff paths/descriptions/placement for the upload step, or the blocker/non-applicability reason screenshots are absent.
  Do not put local screenshot paths in comment bodies.
- `pr_necessity_audit` (for other-authored/unknown PRs): classifications and any draft feedback/questions about intent, correctly-open status, need, or overlapping work
- `summary_comment` (optional): short PR-level comment.
  Use it only when a PR-level comment is explicitly needed, and never to repeat inline-comment content.

### Iterative (when the user asks for one-at-a-time)

If the user says "one at a time", "next comment", or "continue the review":

- Each turn: draft exactly one new review comment for the highest-priority unresolved finding, then stop.
- Output per turn:
  - `Base context:` line (see ~/.agents/skills/k-review/references/shared_rules.md)
  - `Pending review reconciliation:` line when a PR already has current-account pending/submitted review content relevant to this comment
  - Where (file path + line/range when possible)
  - What's wrong (concrete)
  - Why it matters (impact)
  - How to verify (minimal repro/test)
  - Proposed fix (smallest change)
  - `ui_evidence_attachments` when the comment is UI-related and drafted after `/k-deep-review` or `k-agent-live-ui-review`:
    screenshot handoff paths/descriptions/placement, or the blocker/non-applicability reason screenshots are absent.
    Do not put local screenshot paths in the comment body.
- If you need to reply to an existing review thread instead of creating a new comment, switch to PR fix mode for that thread.

## Draft Persistence

- If the user says "consult before sending":
  - keep the full batch draft in a single scratch file under `/tmp/`
  - make it reviewable/editable before posting
  - do not post until explicitly asked
