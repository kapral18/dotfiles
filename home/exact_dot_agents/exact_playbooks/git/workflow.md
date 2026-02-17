# Git Workflow Playbook

Use this playbook for local git repo operations:

- status/diff/log
- staging/unstaging
- branch management
- conflict resolution
- preparing commits

External truth applies:

- verify behavior from the actual repo/version (`git --version`, `git help <cmd>`); do not rely on memory.

When NOT to use:

- GitHub/`gh` operations (PRs, issues, labels, comments, reviews): `~/.agents/playbooks/github/gh_workflow.md`
- Writing-only PR/issue composition: `~/.agents/playbooks/github/compose_pr_general.md`, `~/.agents/playbooks/github/compose_issue_general.md` (or Elastic variants)
- Worktree management (create/switch/remove worktrees, PR worktrees): `~/.agents/playbooks/worktrees/w_workflow.md`

Safety protocol:

- never change git config unless explicitly requested
- never run destructive/irreversible commands (hard resets, force pushes) unless explicitly requested
- never bypass hooks (`--no-verify`, etc.) unless explicitly requested

Approvals:

- always get explicit approval before `git commit`
- always get explicit approval before `git push`

Commit quality:

- use Conventional Commits
- infer `scope` from change surface (best effort)
- each commit must be minimal and atomic, independently reviewable
- commit body bullets are optional; include only when they add signal
- do not invent issue numbers
- do not put `Closes #X` / `Addresses #X` in commit messages; prefer PR description for issue linking
- if the repo uses semantic-release, do not manually version bump unless the repo requires it

Branching:

- branch name: `<type>/<scope>/<kebab-description>` (example: `chore/opencode/update-sop-wording`)
- if upstream is missing, it is OK to set it with `git push -u` (still requires approval)

Merge policy:

- never merge into the base branch via CLI; merges happen via the GitHub UI
