---
name: worktrees
description: |-
  Use when the user mentions ,w or asks to create/switch/open/list/prune/
  remove worktrees, including checking out PRs/issues locally. Prefer ,w
  subcommands over raw git worktree.
---

# ,w Worktree Playbook (Worktrees + tmux)

Primary goal:

- manage local git worktrees using the user's `,w` CLI instead of raw
  `git worktree` commands.

Use this playbook when:

- the user mentions `,w`
- the user asks to create/switch/open/list/prune/remove worktrees
- the user asks to check out a PR locally in a separate worktree

Do not use:

- PR review feedback: `~/.agents/playbooks/review/PLAYBOOK.md`
- GitHub side effects (posting comments/reviews, creating PRs/issues):
  `~/.agents/playbooks/github/PLAYBOOK.md`
- pure git operations unrelated to worktrees (commit/rebase/push):
  `~/.agents/playbooks/git/PLAYBOOK.md`

First actions:

1. Resolve whether the user wants create, switch, list, prune, remove, or PR/
   issue checkout.
2. If the user says "current PR" or "current issue", resolve that identifier
   first via `,gh-prw` or `,gh-issuew`.
3. Prefer the matching `,w` subcommand instead of building the flow from raw
   `git worktree` commands.

Non-negotiables:

- do not create/switch worktrees unless the user explicitly asked for it
- prefer `,w` subcommands over `git worktree`
- do not auto-focus/attach tmux sessions unless the user asked to focus/attach

Common patterns:

- Create a worktree for a PR (non-interactive):
  - `,w prs <pr_number>`
  - `,w prs <pr_url>`
  - "current PR" -> `,gh-prw --number` then `,w prs <number>`

- Create an issue worktree:
  - `,w issue <issue_number>`
  - "current issue" -> `,gh-issuew --number` then `,w issue <number>`

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

# "Current issue" -> worktree:
issue="$(,gh-issuew --number)"
,w issue "$issue"

# Switch to another worktree session:
,w switch kibana
```

Output:

- Report the resulting worktree path/branch and whether tmux focus changed.
- For prune/remove flows, state exactly what was removed.
