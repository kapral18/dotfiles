---
name: k-review
description: "Use for standard-rigor review of local changes, PRs, review threads, PR fixes, or plans."
---

# Review Router

Goal: route standard-rigor review requests to the correct mode while keeping shared rules loaded once.

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
- Mode files reference both files but reuse the already-loaded copies.
- For PR modes, also load `~/.agents/skills/k-review/references/pr_common.md` once.
  Load `~/.agents/skills/k-review/references/pr_context_audits.md` only when `pr_common.md`'s conditional Ambient Topic Exploration or PR Necessity + Correctly-Open Audit gate triggers.
- Keep read-only PR inspection/review inside this router.
  Invoke the `k-github` skill (via the Skill tool) only when the user explicitly asks to post/submit anything to GitHub.
- If the user wants review analysis and GitHub posting in the same request:
  - keep the review router primary
  - draft/verify through review mode first
  - invoke the `k-github` skill via the Skill tool only for the posting step

Standard review uses a bounded reviewer roster as an execution mechanism, not as a separate skill tier:

- finder work is delegated when the active harness can launch workers
- every mode runs adversarial/refutation before acting or drafting
- when refutation keeps yielding findings round after round, switch to `~/.agents/skills/k-converge/SKILL.md`:
  it fixes the exit condition and the correctness-only filter so rounds terminate instead of turning into prose churn
- live UI runs only when UI/runtime evidence is needed; use `k-deep-review` when the user asks for maximum rigor, mandatory deep orchestration, fresh-eyes/context-pack treatment, or the full PR necessity/controller graph

## Secondary Skill Escalation

Load secondary skills only after read/diff evidence proves the surface is in scope.

- Load semantic code search only for base context after the selected mode requires base-branch context.
- Load GitHub workflow only when the user explicitly asks to post/submit anything to GitHub.

## Draft-PR Policy

- Review someone else's draft PR only when the user explicitly asks.
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
Resolve `self` only from verified evidence; a locally checked-out change alone still needs the probes below.

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
  - fix, rather than only comment
  - draft review comments only if the user plans to post self-review notes
- **`other` / `unknown`:**
  - produce draft comments/suggestions only
  - keep code unchanged
  - editing requires the user to explicitly say to fix it (e.g. "fix these" or "take over this branch")

## Mode Selection (Intent + Evidence)

Pick exactly one mode. If ambiguous, ask one fork-closing question and state a default.

### Mode: PR fix (address reviewer feedback)

- Use when the user asks to reply to reviewer comments, address conversations, resolve review threads, or apply requested changes with verification.
- Then open: `~/.agents/skills/k-review/references/pr_fix.md`

### Mode: PR review (initial or continued)

- Use when the user wants an initial PR review, continued review, or verification that a PR fix resolves a bug.
- Role modifies behavior: see Role Detection above and `pr_review.md`.
- Then open: `~/.agents/skills/k-review/references/pr_review.md`

### Mode: Local changes review (working tree, branch delta, or commit range)

- Use when: the user asks to review local changes/diff, a commit range, or a no-PR branch delta.
- If no PR is involved, check `k-light-review`'s Light-Eligibility Predicate before opening `local_changes.md`.
  When self-authored and trigger-free, route to `k-light-review` unless the user explicitly requested full/deep review;
  it is cheaper, not weaker. Otherwise open `~/.agents/skills/k-review/references/local_changes.md`.

### Mode: Plan review (before implementation)

- Use when the user asks to review a plan, design doc, implementation proposal, RFC, issue body, or pasted text rather than a diff.
- Then open: `~/.agents/skills/k-review/references/plan_review.md`

## Disambiguation (If Still Unclear)

If the user's intent is still unclear, resolve via local context (evidence, not guesses):

- If the subject is a document, issue body, or pasted text rather than a code target: plan review mode.
- If not in a git repo:
  - Ask: "Is this a GitHub PR review (send URL/number), a local repo changes review, or a plan/design document review?"
- If in a git repo:
  - Run `git status --porcelain=v1 -b` (read-only, proceed without asking).
  - Independently check both:
    - whether staged/unstaged changes exist
    - whether `,gh-prw --number` resolves a PR for the current branch
  - If both are true: default to local changes mode (verify and fix working tree).
    Note the PR exists in output so the user can switch if needed.
  - If only local changes exist: local changes mode.
  - If only a PR exists: PR review mode.
  - If neither exists: local changes mode (branch delta).
  - Downward routing: when local changes mode applies with no PR, apply the Light-Eligibility Predicate above.
