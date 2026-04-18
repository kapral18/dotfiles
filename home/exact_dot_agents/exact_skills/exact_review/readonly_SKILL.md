---
name: review
description: Review local changes or PRs. Use when reviewing changes, continuing a review, addressing review threads, or rechecking PR-related changes.
---

# Review Router

Goal: route "review" requests to the correct mode while keeping shared rules loaded once.

Contract:

- This router is the entrypoint. If another skill points you here for shared rules, you may skip routing and jump to the relevant section.
- After selecting a mode, open exactly one primary mode file and follow it:
  - `~/.agents/skills/review/references/local_changes.md`
  - `~/.agents/skills/review/references/pr_review.md`
  - `~/.agents/skills/review/references/pr_fix.md`
- Always load `~/.agents/skills/review/references/shared_rules.md` once before entering any mode. Mode files reference shared rules but do not re-load them.
- For PR modes, also load `~/.agents/skills/review/references/pr_common.md` once.
- Load secondary skills only when this router or the selected mode requires them (for example: semantic code search for base context, or GitHub workflow when the user explicitly asks to post).
- Do not invoke the `github` skill for read-only PR inspection/review. Only invoke it (via the Skill tool) when the user explicitly asks to post/submit anything to GitHub.
- If the user wants review analysis and GitHub posting in the same request, the review router stays primary. Draft/verify through review mode first, then invoke the `github` skill via the Skill tool only for the posting step.

## Draft-PR Policy

- Never review someone else's draft PR unless the user explicitly asks.
- If a PR is in draft state and the user did not explicitly request a review, stop and note: "This PR is a draft — skipping review unless you explicitly ask."
- When a draft PR is reviewed (because explicitly asked), apply full thoroughness — a review is a review regardless of draft status.

## PR Detection (Do First When PR Is Involved)

If the user mentions or strongly implies a PR (PR/pull request, PR review, threads, "check my PR comment", "recheck this fix from the PR", etc.):

- First step is PR discovery via `,gh-prw` (read-only):
  - `,gh-prw --number`
  - If it fails once, stop and ask for the PR URL/number.

Continuity rule:

- If the conversation is already clearly in a specific mode, stay in that mode when the user says "continue" / "next" unless they explicitly switch targets.

## Role Detection (Do After PR Detection)

When a PR is involved, determine the user's role before selecting a mode:

- Run: `gh pr view <number> --json author --jq '.author.login'`
- Compare against: `gh api user --jq '.login'`
- If the user is the PR author: they are reviewing their own work (self-review) or addressing feedback.
- If the user is not the PR author: they are reviewing someone else's PR.

This affects mode behavior:

- **Self-review (user is author):** the review should be action-oriented — find issues and fix them in the working tree, not just comment (same as local changes mode). Draft review comments are still useful if the user plans to post them as self-review notes.
- **Reviewing others:** the review produces draft comments/suggestions for the author. Do not change code.

## Mode Selection (Intent + Evidence)

Pick exactly one mode. If ambiguous, ask one fork-closing question and state a default.

### Mode: PR fix (address reviewer feedback)

- Use when: the user asks to reply to reviewer comments, address conversations, resolve existing review threads, OR apply requested changes from reviewer feedback by iterating on code with verification ("apply the requested changes", "let's fix review comments", "one comment at a time until resolved", "address threads", "reply to reviewers").
- Then open: `~/.agents/skills/review/references/pr_fix.md`

### Mode: PR review (initial or continued)

- Use when: the user wants an initial full PR review, wants to continue a review with the next comment, or wants to recheck/verify whether a PR fix resolves a bug ("review this PR", "what's the next comment", "continue the review", "does this PR fix it", "can you recheck", "verify this fix").
- Role modifies behavior: see Role Detection above and `pr_review.md` for details.
- Then open: `~/.agents/skills/review/references/pr_review.md`

### Mode: Local changes review (working tree, branch delta, or commit range)

- Use when: the user asks to review local changes/diff, review a specific commit range, or when there is no PR for the current branch and the user still wants a review.
- This mode verifies and fixes: findings are resolved in the working tree immediately, not drafted as comments.
- Then open: `~/.agents/skills/review/references/local_changes.md`

## Disambiguation (If Still Unclear)

If the user's intent is still unclear, resolve via local context (do not guess):

- If not in a git repo:
  - Ask: "Is this a GitHub PR review (send URL/number), or a local repo changes review?"
- If in a git repo:
  - Run `git status --porcelain=v1 -b` (read-only, do not ask to proceed).
  - Independently check both:
    - whether staged/unstaged changes exist
    - whether `,gh-prw --number` resolves a PR for the current branch
  - If both are true: default to local changes mode (verify and fix working tree). Note the PR exists in output so the user can switch if needed.
  - If only local changes exist: local changes mode.
  - If only a PR exists: PR review mode.
  - If neither exists: local changes mode (branch delta).
