# ,w Worktree Playbook (Worktrees + tmux)

Primary goal:

- manage local git worktrees using the user's `,w` CLI instead of raw `git worktree` commands.

Use this playbook when:

- the user mentions `,w`
- the user asks to create/switch/open/list/prune/remove worktrees
- the user asks to check out a PR locally in a separate worktree

When NOT to use:

- PR review feedback: `~/.agents/playbooks/review/router.md`
- GitHub side effects (posting comments/reviews, creating PRs/issues): `~/.agents/playbooks/github/gh_workflow.md`
- pure git operations unrelated to worktrees (commit/rebase/push): `~/.agents/playbooks/git/workflow.md`

Non-negotiables:

- do not create/switch worktrees unless the user explicitly asked for it
- prefer `,w` subcommands over `git worktree`
- do not auto-focus/attach tmux sessions unless the user asked to focus/attach

Common patterns:

- Create a worktree for a PR (non-interactive):
  - `,w prs <pr_number>`
  - `,w prs <pr_url>`
  - "current PR" -> `,gh-prw --number` then `,w prs <number>`

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
pr="$(,gh-prw --number)"
,w prs "$pr"

# Switch to another worktree session:
,w switch kibana
```
