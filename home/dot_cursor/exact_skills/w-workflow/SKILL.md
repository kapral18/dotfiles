---
name: w-workflow
description: "Worktree + tmux workflow via the `,w` CLI: create PR worktrees, create branch worktrees, list/switch/open, prune/doctor/remove. Use when the user mentions `,w` or asks to create/switch/remove a worktree. Do NOT use for PR review feedback or GitHub posting."
---

# ,w Workflow (Worktrees + tmux)

Primary goal: manage local git worktrees using the user's `,w` CLI instead of raw `git worktree` commands.

When to use:

- The user mentions `,w`.
- The user asks to create/switch/open/list/prune/remove worktrees.
- The user asks to check out a PR locally in a separate worktree.

When NOT to use:

- PR review feedback (drafting comments): use `github-pr-review-*`.
- GitHub side effects (posting comments/reviews, creating PRs/issues): use `github-gh-workflow`.
- Pure git operations unrelated to worktrees (commit/rebase/push): use `git-workflow`.

Non-negotiables:

- Do not create/switch worktrees unless the user explicitly asked for it.
- Prefer `,w` subcommands over `git worktree`.
- Do not auto-focus/attach tmux sessions unless the user asked to focus/attach.

Common patterns:

- Create a worktree for a PR (non-interactive):
  - `,w prs <pr_number>`
  - `,w prs <pr_url>`
  - If the user means "current PR" and you need the number: `gh prw --number` then `,w prs <number>`

- Create a worktree for a branch:
  - `,w add <branch_name> [base_branch]`

- List worktrees:
  - `,w ls`

- Switch between worktree tmux sessions:
  - `,w switch [query...]`

- Focus an existing worktree session by branch/path:
  - `,w open <branch|path>`

- Hygiene:
  - `,w prune`
  - `,w doctor`
  - `,w remove`

Examples:

```bash
# Create a PR worktree (no tmux focus by default):
,w prs 252693

# Create and focus the tmux session (only when asked):
,w prs --focus 252693

# "Current PR" -> worktree:
pr="$(gh prw --number)"
,w prs "$pr"

# Switch to another worktree session:
,w switch kibana
```
