# Git Workflow Playbook

Use this playbook for local git repo operations:

- status/diff/log
- staging/unstaging
- branch management
- conflict resolution
- preparing commits

External truth applies:

- verify behavior from the actual repo/version (`git --version`, `git help <cmd>`); do not rely on memory.

Do not use:

- GitHub/`gh` operations (PRs, issues, labels, comments, reviews): `~/.agents/playbooks/github/gh_workflow.md`
- Writing-only PR/issue composition: `~/.agents/playbooks/github/compose_pr_general.md`, `~/.agents/playbooks/github/compose_issue_general.md` (or Elastic variants)
- Worktree management (create/switch/remove worktrees, PR worktrees): `~/.agents/playbooks/worktrees/w_workflow.md`

First actions:

1. Establish repo state with the smallest relevant read-only probes (`git
   status`, `git diff`, `git log`, branch name).
2. Use the actual repo's history/configuration as the source of truth for
   workflow conventions.
3. Before any commit/push, restate the exact command and get approval.

Safety protocol:

- never change git config unless explicitly requested
- never run destructive/irreversible commands (hard resets, plain `--force`
  pushes) unless explicitly requested
- never bypass hooks (`--no-verify`, etc.) unless explicitly requested

Approvals:

- always get explicit approval before `git commit`
- always get explicit approval before `git push`

Push policy (mandatory):

- interpret a user request to "push" as explicit approval for
  `git push --force-with-lease`
- prefer explicit remote/branch in the restated command (example:
  `git push --force-with-lease origin <branch>`)
- if upstream is missing, `git push --force-with-lease -u <remote> <branch>`
  is allowed (still requires approval)
- never run `git pull`, `git pull --rebase`, `git rebase <remote>/<branch>`,
  or `git merge <remote>/<branch>` automatically before pushing
- if push fails due to divergence/non-fast-forward/lease checks, stop and ask
  for user direction; do not reconcile on your own

Commit quality:

- use Conventional Commits when the repo already uses them; otherwise match the
  repo's existing commit style
- infer `scope` from change surface (best effort)
- each commit must be minimal and atomic, independently reviewable
- commit body bullets are optional; include only when they add signal
- do not invent issue numbers
- do not put `Closes #X` / `Addresses #X` in commit messages; prefer PR description for issue linking
- if the repo uses semantic-release, do not manually version bump unless the repo requires it

Branching:

- follow repo/team branch naming if one exists; otherwise default to
  `<type>/<scope>/<kebab-description>` (example:
  `chore/opencode/update-sop-wording`)

Merge policy:

- never merge into the base branch via CLI; merges happen via the GitHub UI

Output:

- Summarize repo state, the command(s) run, and the verification result.
- If a requested action would be destructive or cross into another playbook's
  scope, stop and route instead of improvising.
