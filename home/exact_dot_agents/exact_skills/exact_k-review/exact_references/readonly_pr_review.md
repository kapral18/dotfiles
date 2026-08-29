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

Check Role Detection from the router (`SKILL.md`):

- **Reviewing others (`authorship: other` or `unknown`):**
  - draft comments/suggestions
  - do not change code
  - run the PR Necessity + Correctly-Open Audit in `pr_context_audits.md`
  - apply the Findings-Set Audit (`judging_pipeline.md`) to surviving PR-diff candidate findings before drafting
  - surface redundancy / verbosity / semantic + logical duplication / gaps as read-only finding-set findings
- **Self-review (user is the author):**
  - find issues and fix them in the working tree immediately
  - follow local changes mode behavior
  - after quality gates pass, run the Post-Review Stage over the fix diff
  - draft review comments only if the user explicitly wants self-review notes to post

## Complete Pass Before Drafting (Mandatory)

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
- run Ambient Topic Exploration in pr_context_audits.md when disagreement, unclear shared understanding, or missing topic history matters
- run the PR Necessity + Correctly-Open Audit in pr_context_audits.md when reviewing someone else's PR or when authorship is unknown
- run Existing Pending Review Reconciliation in pr_common.md before producing the final review draft
- all review threads/replies (end-to-end)
- full diff and enclosing files (never review diff hunks in isolation; inspect surrounding callers and sibling consumers)
- historical provenance: in large repos, run targeted line-bounded probes (`git blame -L <start>,<end>` / `git log -n 5 -L`) on modified existing logic to understand why it was built and ensure past bug fixes are preserved
- targeted local verification for risky claims (see pr_common.md)

On later turns (iterative/continued):

- keep working from the internal findings queue
- do not re-read everything unless needed
- if the PR changed, run the intake gate for changed artifacts before relying on the prior queue
- if a new comment/link/reference appears, run the intake gate for that artifact before relying on the prior queue

## Base-Branch Context

Follow the base-branch context gate in `shared_rules.md`. This is mandatory.

## Agent-Assisted Review Contract

- Launch one `reviewer`/`review-worker` `correctness-regressions` lane for the PR diff when the harness supports subagents;
  add one extra lane only for an independently evidenced risk class.
  Select both from `lanes.md` and paste the chosen lane's `Lens skill` line and `Checks` list into the worker's scope packet;
  workers never load `lanes.md`.
  Run any repo-wide suite or full build once here and pass the result into every scope packet — lanes are told not to repeat shared work.
  If the harness cannot delegate, run the finder pass inline and report `agent_lane=inline-degraded`.
  Generation recall is bounded by perspective: refuters prune candidates but never expand them, and most confirmed defects are caught by exactly one reviewer perspective.
  When the model resolver supports per-lane selection at equal capability (SOP §3.7), prefer two finder lanes from different model families;
  otherwise one cross-family finder over same-family; never leave controller, finder, and refuter all same-family.
  Report `finder_family=same|cross|two-cross` alongside `adversarial=`.
  Launch the cross-family lane through the harness's `review-worker-cross` profile where one is fielded;
  on single-vendor harnesses it resolves back to the standard lane model — report that honestly.
- Run live UI only when UI/runtime evidence is needed for a candidate and a startable runtime is available;
  use `k-deep-review` for the full live-UI target-packet/controller graph.
- Before adversarial verification, run the candidate queue through the Findings-Set Audit, Deduplication + Truth Filter, and Existing Pending Review Reconciliation; only implementation-verified findings that are not covered, not duplicated, and not dropped by the Replacement/Migration Parity Gate remain, and any current-account pending review is merged into one final payload.
- If the audited candidate set is empty, skip adversarial work and report `Adversarial verification: skipped (no candidates after findings audit)`.
- Otherwise, run `adversarial-verifier` over the audited candidate set before drafting;
  if no verifier lane is available, run the Candidate Refutation Ladder inline and report `adversarial=inline-degraded`.
- Draft highest-risk items first.

## Output Mode

### Batch (default)

Return a `Pending review draft` containing:

- `Base context:` line (see shared_rules.md)
- `Pending review reconciliation:` line (see pr_common.md)
- `review_submission`: the exact submit `event` recommendation and PR-level review `body`;
  keep the body as a short acknowledgement (for example, `Looks good.` for a clean approval, or `Left inline feedback.` when comments exist) and include it in any posting approval payload.
  Do not repeat, summarize, or enumerate details that are already in inline comments.
- `inline_comments`: one draft per finding worth commenting, each with:
  - Where (file path + line/range when possible)
  - Comment body
  - Why it matters (1-2 lines)
  - How to verify (minimal)
  - Proposed fix (smallest change)
- `ui_evidence_attachments`: for UI-related findings drafted after `/k-deep-review` or `live-ui-review`, screenshot handoff paths/descriptions/placement for the upload step, or the blocker/non-applicability reason screenshots are absent.
  Do not put local screenshot paths in comment bodies.
- `pr_necessity_audit` (for other-authored/unknown PRs): classifications and any draft feedback/questions about intent, correctly-open status, need, or overlapping work
- `summary_comment` (optional): short PR-level comment.
  Use it only when a PR-level comment is explicitly needed, and never to repeat inline-comment content.

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
  - `ui_evidence_attachments` when the comment is UI-related and drafted after `/k-deep-review` or `live-ui-review`:
    screenshot handoff paths/descriptions/placement, or the blocker/non-applicability reason screenshots are absent.
    Do not put local screenshot paths in the comment body.
- If you need to reply to an existing review thread instead of creating a new comment, switch to PR fix mode for that thread.

## Draft Persistence

- If the user says "consult before sending":
  - keep the full batch draft in a single scratch file under `/tmp/`
  - make it reviewable/editable before posting
  - do not post until explicitly asked
