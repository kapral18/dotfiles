# Mode: PR Review

Use when the user wants a PR review (initial or continued), gives a PR and says "review", or asks whether a PR fix resolves a bug ("does this PR fix it", "recheck", "is it resolved on the updated branch").
To apply reviewer feedback (code changes plus thread replies), use `~/.agents/skills/k-review/references/pr_fix.md`.

Load `~/.agents/skills/k-review/references/pr_common.md` at the first gate that names it.

## Authorship

Resolve authorship and write scope per `~/.agents/skills/k-review/references/authorship.md`; that policy decides whether to fix findings.
For `other` or `unknown`, establish PR intent and necessity with `~/.agents/skills/k-review/references/pr_context_audits.md`.

## First pass (complete before drafting)

1. GitHub Context Intake + Reference Resolution in `pr_common.md`: full body, every comment, reply, thread, media item, and the references that settle material questions.
   This gate blocks drafting.
2. Ambient Topic Exploration (`pr_context_audits.md`) when disagreement, unclear shared understanding, or missing topic history matters.
3. PR Necessity + Correctly-Open Audit (`pr_context_audits.md`) for someone else's PR or unknown authorship.
4. The full diff per `~/.agents/skills/k-review/references/pr_snapshot.md`, then enclosing files, callers, and sibling consumers.
5. The Base-Branch Context Gate in `~/.agents/skills/k-review/references/shared_rules.md`, with line-bounded history probes on modified existing logic.
6. Targeted local verification for risky claims (`pr_common.md`).
7. Existing Pending Review Reconciliation (`pr_common.md`) before the final draft.

On later turns, work from the queue (`shared_rules.md` Review Queue).
Run the Drift check in `pr_snapshot.md` first; only changed artifacts go through intake again.

## Output

### Batch (default)

A `Pending review draft` containing:

- `Base context:` line and `Pending review reconciliation:` line
- `review_submission`: the recommended submit `event` and a short PR-level `body` (`Looks good.` for a clean approval, `Left inline feedback.` when comments exist).
  Do not repeat inline content.
- `inline_comments`: one per finding worth commenting — where (file and line or range), comment body, why it matters (1–2 lines), how to verify, smallest fix
- `ui_evidence_attachments`: for UI findings, screenshot paths, descriptions, and placement for the upload step, or why screenshots are absent.
  Never put local paths in comment bodies.
- `pr_necessity_audit` for someone else's PR or unknown authorship
- `summary_comment` only when a PR-level comment is explicitly needed

### Iterative ("one at a time", "next comment", "continue the review")

Each turn, draft one comment for the highest-priority open finding and stop.
Include the `Base context:` line, the reconciliation line when relevant, where, what is wrong, why it matters, how to verify, the smallest fix, and UI evidence when relevant.
To reply to an existing thread instead, switch to PR fix mode for that thread.

## Draft persistence

When the user says "consult before sending", keep the full draft in one scratch file under `/tmp/k-review/` and post nothing until asked.
