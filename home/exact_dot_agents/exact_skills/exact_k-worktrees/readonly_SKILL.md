---
name: k-worktrees
description: "Use when managing worktrees with ,w or ,gh-worktree: create, switch, open, list, prune, remove, or PR checkout."
---

# ,w Worktree Skill (Worktrees + tmux)

Primary goal:

- manage local git worktrees using the user's `,w` CLI instead of raw `git worktree` commands.
  - keep command boundaries explicit: `,gh-worktree` handles repo routing/bootstrap;
    `,w` handles worktree operations inside a resolved repo.

Do not use:

- PR review feedback: `~/.agents/skills/k-review/SKILL.md`
- GitHub side effects (posting comments/reviews, creating PRs/issues): `~/.agents/skills/k-github/SKILL.md`
- pure git operations unrelated to worktrees (commit/rebase/push): `~/.agents/skills/k-git/SKILL.md`

First actions:

1. Resolve whether the user wants create, switch, list, prune, remove, or PR/ issue checkout.
2. If the user says "current PR" or "current issue", resolve that identifier first via `,gh-prw` or `,gh-issuew`.
3. Choose the entrypoint:
   - if the ask starts from a GitHub PR/issue, repo slug, URL, or may require local repo resolution/bootstrap -> use `,gh-worktree`
   - for GitHub issue worktrees in non-interactive agent contexts -> use `,gh-worktree issue <owner/repo> <issue_number> --branch <branch-base-name>`
   - if repo is already resolved/current and the ask is a direct in-repo worktree op -> use `,w`
4. Prefer the matching `,gh-worktree` / `,w` subcommand instead of building the flow from raw `git worktree` commands.

Non-negotiables:

- do not create/switch worktrees unless the user explicitly asked for it
- prefer `,w` subcommands over `git worktree`
- do not auto-focus/attach tmux sessions unless the user asked to focus/attach

Common patterns:

- Cross-repo GitHub entrypoint (shared with tmux/gh-dash flows):
  - `,gh-worktree pr <owner/repo> <pr_number> [--focus] [--quiet]`
  - `,gh-worktree issue <owner/repo> <issue_number> [--focus] [--quiet] [--branch <name>]`
  - in non-interactive agent contexts, use `,gh-worktree issue ... --branch <name>` for GitHub issues by default
  - use `--repo-path` when you already have a repo path hint from tooling output

- Create a worktree for a PR (non-interactive):
  - `,w prs <pr_number>`
  - `,w prs <pr_url>`
  - "current PR" -> `,gh-prw --number` then `,w prs <number>`

- Create an issue worktree:
  - GitHub issue from agent context -> `,gh-worktree issue <owner/repo> <issue_number> --branch <branch-base-name>`
  - already inside the correct repo -> `,w issue -b <branch-base-name> <issue_number>`
  - "current issue" -> `,gh-issuew --number` plus repo resolution, then `,gh-worktree issue <owner/repo> <number> --branch <branch-base-name>`

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
repo="$(gh repo view --json nameWithOwner --jq '.nameWithOwner')"
issue="$(,gh-issuew --number)"
,gh-worktree issue "$repo" "$issue" --branch feat/my-change

# Switch to another worktree session:
,w switch my-feature
```

Output:

- Report the resulting worktree path/branch and whether tmux focus changed.
- For prune/remove flows, state exactly what was removed.
