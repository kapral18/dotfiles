---
name: k-review
description: "Use when reviewing local changes or PRs, continuing a review, addressing review threads, rechecking PR-related changes, or reviewing a plan/design document before implementation."
---

# Review Router

Goal: route "review" requests to the correct mode while keeping shared rules loaded once.

Contract:

- This router is the entrypoint. If another skill points you here for shared rules, you may skip routing and jump to the relevant section.
- After selecting a mode, open exactly one primary mode file and follow it:
  - `~/.agents/skills/k-review/references/local_changes.md`
  - `~/.agents/skills/k-review/references/pr_review.md`
  - `~/.agents/skills/k-review/references/pr_fix.md`
  - `~/.agents/skills/k-review/references/plan_review.md`
- Before entering any mode, load once:
  - `~/.agents/skills/k-review/references/judging_core.md`
  - `~/.agents/skills/k-review/references/shared_rules.md`
- Mode files reference both files but do not re-load them.
- For PR modes, also load `~/.agents/skills/k-review/references/pr_common.md` once.
- Do not invoke the `k-github` skill for read-only PR inspection/review.
  Only invoke it (via the Skill tool) when the user explicitly asks to post/submit anything to GitHub.
- If the user wants review analysis and GitHub posting in the same request:
  - keep the review router primary
  - draft/verify through review mode first
  - invoke the `k-github` skill via the Skill tool only for the posting step

## Secondary Skill Escalation

Do not load secondary skills until read/diff evidence proves the surface is in scope.

- Load semantic code search only for base context after the selected mode requires base-branch context.
- Load GitHub workflow only when the user explicitly asks to post/submit anything to GitHub.

## Draft-PR Policy

- Never review someone else's draft PR unless the user explicitly asks.
- If a PR is in draft state and the user did not explicitly request a review, stop and note: "This PR is a draft —
  skipping review unless you explicitly ask."
- When a draft PR is reviewed (because explicitly asked), apply full thoroughness — a review is a review regardless of draft status.

## PR Detection (Do First When PR Is Involved)

If the user mentions or strongly implies a PR (PR/pull request, PR review, threads, "check my PR comment", "recheck this fix from the PR", etc.):

- First step is PR discovery via `,gh-prw` (read-only):
  - `,gh-prw --number`
  - If it fails once, stop and ask for the PR URL/number.

Continuity rule:

- If the conversation is already clearly in a specific mode, stay in that mode when the user says "continue" / "next" unless they explicitly switch targets.

## Role Detection / Authorship (Mandatory In Every Mode)

Resolve `authorship` before selecting a mode.

Allowed values:

- `self`
- `other`
- `unknown`

Exception: plan review mode has no code target. Record `authorship: n/a`, skip the git/`gh` probes below, and produce feedback only.

This input gates whether the review may edit code. Resolve it in the local/branch path too.
Never default to `self` just because the change is checked out locally.

When a PR is involved:

- Run: `gh pr view <number> --json author --jq '.author.login'`
- Compare against: `gh api user --jq '.login'`
- Match -> `self`; mismatch -> `other`; cannot resolve -> `unknown`.

When there is no PR (local changes / branch-delta / commit-range review):

- Identify the current user: `gh api user --jq '.login'` (fall back to `git config user.email` if `gh` is unavailable).
- Check the branch's tracked remote with bounded read-only git probes in large repositories:
  - `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false rev-parse --abbrev-ref --symbolic-full-name @{u}`
  - `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false remote -v` for that remote's URL/owner
- A branch tracking another person's fork is `other` (e.g. `someoneelse/<branch>`).
- Check authorship of the commits under review: `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false log --format='%an <%ae>' <base>..HEAD`.
  Commits authored by someone other than the current user make it `other`.
- Only uncommitted/staged working-tree changes, or commits/branch owned by the current user, resolve to `self`.
  If it cannot be verified, it is `unknown`.

This affects mode behavior:

- **`self` (user owns the change):**
  - find issues and fix them in the working tree
  - do not only comment
  - draft review comments only if the user plans to post self-review notes
- **`other` / `unknown`:**
  - produce draft comments/suggestions only
  - do not change code
  - editing requires the user to explicitly say to fix it (e.g. "fix these" or "take over this branch")

## Mode Selection (Intent + Evidence)

Pick exactly one mode. If ambiguous, ask one fork-closing question and state a default.

### Mode: PR fix (address reviewer feedback)

- Use when the user asks to:
  - reply to reviewer comments
  - address conversations
  - resolve existing review threads
  - apply requested changes from reviewer feedback by iterating on code with verification
- Example phrases:
  - "apply the requested changes"
  - "let's fix review comments"
  - "one comment at a time until resolved"
  - "address threads"
  - "reply to reviewers"
- Then open: `~/.agents/skills/k-review/references/pr_fix.md`

### Mode: PR review (initial or continued)

- Use when the user wants:
  - an initial full PR review
  - to continue a review with the next comment
  - to recheck/verify whether a PR fix resolves a bug
- Example phrases:
  - "review this PR"
  - "what's the next comment"
  - "continue the review"
  - "does this PR fix it"
  - "can you recheck"
  - "verify this fix"
- Role modifies behavior: see Role Detection above and `pr_review.md` for details.
- Then open: `~/.agents/skills/k-review/references/pr_review.md`

### Mode: Local changes review (working tree, branch delta, or commit range)

- Use when: the user asks to review local changes/diff, review a specific commit range, or when there is no PR for the current branch and the user still wants a review.
- This mode verifies and fixes: findings are resolved in the working tree immediately, not drafted as comments.
- Then open: `~/.agents/skills/k-review/references/local_changes.md`

### Mode: Plan review (before implementation)

- Use when the user asks to review a plan, design doc, implementation proposal, or RFC —
  a document, issue body, or pasted text rather than a diff.
- Example phrases:
  - "review this plan"
  - "check my implementation plan"
  - "poke holes in this design"
- Authorship and fix gating do not apply (no code target); the output is plan feedback.
- Then open: `~/.agents/skills/k-review/references/plan_review.md`

## Disambiguation (If Still Unclear)

If the user's intent is still unclear, resolve via local context (do not guess):

- If the subject is a document, issue body, or pasted text rather than a code target: plan review mode.
- If not in a git repo:
  - Ask: "Is this a GitHub PR review (send URL/number), a local repo changes review, or a plan/design document review?"
- If in a git repo:
  - Run `git status --porcelain=v1 -b` (read-only, do not ask to proceed).
  - Independently check both:
    - whether staged/unstaged changes exist
    - whether `,gh-prw --number` resolves a PR for the current branch
  - If both are true: default to local changes mode (verify and fix working tree).
    Note the PR exists in output so the user can switch if needed.
  - If only local changes exist: local changes mode.
  - If only a PR exists: PR review mode.
  - If neither exists: local changes mode (branch delta).
  - Downward routing: when local changes mode applies and no PR exists, check the Light-Eligibility Predicate in `~/.agents/skills/k-light-review/SKILL.md`.
    If the change is self-authored and none of its escalation triggers hold, note that `k-light-review` is the cheaper equivalent (opt-in base context, no PR/GitHub scaffolding) and offer it before running the full local-changes machinery.
