# Review Drafting And Delivery

Loaded from `shared_rules.md` before drafting public-ready review content, recommending a PR verdict, or posting.
The intake publication and authorship constraints remain in `shared_rules.md`; this reference grants no additional permission.

## Draft Style (Public-Ready)

- Tone, concision, and response triage are centralized in `~/.agents/skills/k-communication/SKILL.md`.
- Follow it for all:
  - comment wording
  - reply wording
  - description wording
- The rules below are review-specific additions only.
- No headline summaries or category prefixes (exception: `nit:` allowed only for true nits).
- Keep explanations simple; prefer tiny examples, pseudocode, or ASCII sketches.
- Skip redundant "Ref:" links when the comment is already attached to the exact line.
- Keep anchoring/tooling limitations out of the comment body ("can't anchor inline", "not in diff hunks").
- For UI-related comments, replies, or PR-level feedback drafted after `/k-deep-review` or `k-agent-live-ui-review`, keep the screenshot handoff outside the body as UI evidence attachments.
  If required screenshot evidence is missing, report that criterion as blocked instead of drafting unsupported UI feedback.
  Final reviewers MUST NOT rerun a worker or restart verification. The root handles any authorized evidence recovery under SOP §3.5.
  Never put local screenshot paths in GitHub comment, reply, review, or PR-level bodies.
- In review comment bodies, whenever you reference code, use a clickable source link to the exact location on the PR head SHA.
- Code references include:
  - file path
  - function
  - symbol
  - line/range
  - snippet location
- Do not leave plain unlinked code/file references.
- **Commit references must be clickable links, never bare hashes or inline code.**
- Use the full GitHub URL:
  - `https://github.com/OWNER/REPO/commit/FULL_SHA`
  - or `/pull/NUM/commits/FULL_SHA` when referencing a PR commit
- Resolve `OWNER/REPO` from the current repo.
- Expand short hashes to full SHA before linking.
- Use `suggestion` blocks only when confident the replacement matches the exact anchored line(s).

## Pending Review Semantics (Definition + Content Boundary)

Terminology used in these skills:

- "pending review" means a GitHub PR review whose API `state` is `PENDING` (draft):
  - it is visible only to the reviewer who created it until they submit it (COMMENT/APPROVE/REQUEST_CHANGES)
  - it is _not_ visible to the PR author or other reviewers while pending
  - assume everything in it may become public once submitted; draft accordingly

Content boundary:

- A pending review must contain only public-ready review content: objective, presentable, and directly related to the code under review.
- Never include:
  - agent internal reasoning
  - excerpts of internal conversation
  - tool outputs
  - meta-justifications
- The PR author should remain unaware that internal discussion exists.
- Prefer concrete fixes:
  - best: GitHub `suggestion` blocks with exact replacement code
  - otherwise: small code snippets or precise, actionable steps (concrete over vague descriptions).

## Review Verdict (PR Review Mode Only)

After all findings are drafted, recommend an overall verdict from `authorship`, severity, and `author_relation`:

- **Self-review** (`authorship: self`):
  - Fix authority follows write scope per `authorship.md`: findings are fixed in the same pass when the current packet holds write scope over the affected path (the default for root executing inline); a final-Verify-stage packet stays read-only by category regardless of authorship — report remaining findings there, and the root applies SOP §3.5 when existing authority covers repair.
  - **Comment only** if the user explicitly asks to post self-review notes with remaining non-blocking findings.
  - **Approve** when no findings remain.
  - Do not request changes on the user's own PR from this flow.
- **Immediate-team author**:
  - **Request changes** only for a CRITICAL blocker that must be addressed before merge.
  - **Comment only** when findings remain below CRITICAL. Trust teammates to judge whether comment-level feedback should block.
  - **Approve** when no findings remain.
- **Outside or unknown-team author**:
  - **Request changes** for CRITICAL or HIGH findings that must be addressed before merge.
  - **Comment only** for MEDIUM findings.
  - **Approve with comments** for LOW findings or true nits.
  - **Approve** when no findings remain.

State the recommendation and one short reason.

Example:

- `Verdict: request changes — the unchecked error on line 42 can cause silent data loss`

Apply the SOP §3.8 authorization and conditions to submit the verdict; do not treat a recommendation as authority by itself.

## Posting Boundary

- Draft unapproved authored content in chat first. Apply SOP §§3.8 and 3.5 for authorization persistence and scoped failure termination.
- If the user asks to post/submit/apply anything to GitHub:
  - keep the draft content from the review mode
  - then invoke the `k-github` skill via the Skill tool
  - confirm explicit approval only when existing SOP §3.8 authorization does not already cover the exact target, payload, and effect
- Human-Visible Publication Gate (SOP, `~/AGENTS.md`):
  - explicit approval or an approval packet defined by the relevant skill/reference is required for any human-visible target
  - automation carve-outs are the SOP-defined packets only; do not infer new ones here
  - see the scoped batch in `pr_fix.md`
  - bot-authored threads may be auto-replied/auto-resolved only inside a flow the user already invoked
