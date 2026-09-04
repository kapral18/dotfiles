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
  If screenshot evidence is missing without a valid blocker or non-applicability result, block/rerun instead of drafting text-only UI feedback.
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
  - Fix issues in the working tree before recommending a GitHub review verdict.
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

The user decides whether to actually submit the verdict.

## Posting Boundary

- Draft in chat first.
- If the user asks to post/submit/apply anything to GitHub:
  - keep the draft content from the review mode
  - then invoke the `k-github` skill via the Skill tool
  - confirm explicit approval or an approval packet defined by the relevant skill/reference for the GitHub side effect
- Human-Visible Publication Gate (SOP, `~/AGENTS.md`):
  - explicit approval or an approval packet defined by the relevant skill/reference is required for any human-visible target
  - automation carve-outs are the SOP-defined packets only; do not infer new ones here
  - see `pr_fix.md` Drain Mode
  - bot-authored threads may be auto-replied/auto-resolved only inside a flow the user already invoked
