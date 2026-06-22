# Mode: PR Review

Precondition:

- You already loaded `~/.agents/skills/review/SKILL.md`.
- Follow `~/.agents/skills/review/references/judging_core.md` and `~/.agents/skills/review/references/shared_rules.md` (loaded once by the router; do not re-load).
- Follow `~/.agents/skills/review/references/pr_common.md` for PR setup, media evidence, comment placement, anchoring, deep links, and local verification.

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

- If the user wants to apply requested changes from reviewer feedback (code changes + replies per thread), use `~/.agents/skills/review/references/pr_fix.md` instead.

## Role-Dependent Behavior

Check Role Detection from the router (`SKILL.md`):

- **Reviewing others (`authorship: other` or `unknown`):**
  - draft comments/suggestions
  - do not change code
  - run the PR Necessity + Correctly-Open Audit in `pr_common.md`
  - apply the Post-Review Lens (`judging_core.md`) to the PR diff
  - surface redundancy / verbosity / semantic + logical duplication / gaps as read-only findings
- **Self-review (user is the author):**
  - find issues and fix them in the working tree immediately
  - follow local changes mode behavior
  - after quality gates pass, run the Post-Review Stage over the fix diff
  - draft review comments only if the user explicitly wants self-review notes to post

## Complete Pass Before Drafting (Do Not Skip)

On the first turn (or when starting a fresh review):

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
- run the PR Necessity + Correctly-Open Audit in pr_common.md when reviewing someone else's PR or when authorship is unknown
- run Existing Pending Review Reconciliation in pr_common.md before producing the final review draft
- all review threads/replies (end-to-end)
- full diff
- targeted local verification for risky claims (see pr_common.md)

On later turns (iterative/continued):

- keep working from the internal findings queue
- do not re-read everything unless needed
- if the PR changed, run the intake gate for changed artifacts before relying on the prior queue
- if a new comment/link/reference appears, run the intake gate for that artifact before relying on the prior queue

## Base-Branch Context

Follow the base-branch context gate in `shared_rules.md`. This is mandatory.

## Review Contract

- Build a complete internal findings queue ordered by severity.
- Before drafting, run the queue through the Deduplication + Truth Filter and Existing Pending Review Reconciliation in `pr_common.md`; only implementation-verified findings that are not covered, not duplicated, and not dropped by the Replacement/Migration Parity Gate remain, and any current-account pending review is merged into one final payload.
- Draft highest-risk items first.

## Output Mode

### Batch (default)

Return a `Pending review draft` containing:

- `Base context:` line (see shared_rules.md)
- `Pending review reconciliation:` line (see pr_common.md)
- `inline_comments`: one draft per finding worth commenting, each with:
  - Where (file path + line/range when possible)
  - Comment body
  - Why it matters (1-2 lines)
  - How to verify (minimal)
  - Proposed fix (smallest change)
- `pr_necessity_audit` (for other-authored/unknown PRs): classifications and any draft feedback/questions about intent, correctly-open status, need, or overlapping work
- `summary_comment` (optional): short PR-level comment

### Iterative (when the user asks for one-at-a-time)

If the user says "one at a time", "next comment", or "continue the review":

- Each turn: draft exactly one new review comment for the highest-priority unresolved finding, then stop.
- Output per turn:
  - `Base context:` line (see shared_rules.md)
  - `Pending review reconciliation:` line when a PR already has current-account pending/submitted review content relevant to this comment
  - Where (file path + line/range when possible)
  - What's wrong (concrete)
  - Why it matters (impact)
  - How to verify (minimal repro/test)
  - Proposed fix (smallest change)
- If you need to reply to an existing review thread instead of creating a new comment, switch to PR fix mode for that thread.

## Draft Persistence

- If the user says "consult before sending":
  - keep the full batch draft in a single scratch file under `/tmp/`
  - make it reviewable/editable before posting
  - do not post until explicitly asked
