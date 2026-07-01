---
name: git
description: "Use when doing local git operations: status, diff, log, staging, branches, commits, pushes, rebases, or conflicts."
---

# Git Workflow Skill

External truth applies:

- verify behavior from the actual repo/version (`git --version`, `git help <cmd>`); do not rely on memory.

Do not use:

- GitHub/`gh` operations (PRs, issues, labels, comments, reviews): `~/.agents/skills/github/SKILL.md`
- Writing-only PR/issue composition: `~/.agents/skills/compose-pr/SKILL.md`, `~/.agents/skills/compose-issue/SKILL.md`
- Worktree management (create/switch/remove worktrees, PR worktrees): `~/.agents/skills/worktrees/SKILL.md`

First actions:

1. Establish repo state with the smallest relevant read-only probes (`git status`, `git diff`, `git log`, branch name).
2. Use the actual repo's history/configuration as the source of truth for workflow conventions.
3. Before any commit/push, restate the exact command and get approval.

Large-repo probe safety:

- For initial status/diff/routing probes in large repositories, prefer bounded read-only commands:
  - `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false status --short --branch`
  - `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false diff --name-only`
- If a plain `git status`, `git diff`, or branch/upstream probe produces no output after one short wait, stop that command and rerun the bounded form above.
  Do not keep waiting on the same git process.
- Keep the first probe narrow: status, branch, upstream, changed paths, and the smallest commit range needed for the task.

Safety protocol:

- never change git config unless explicitly requested
- never run destructive/irreversible commands (hard resets, plain `--force` pushes) unless explicitly requested
- never bypass hooks (`--no-verify`, etc.) unless explicitly requested

Approvals:

- always get explicit approval before `git commit`
- always get explicit approval before `git push`

Push policy (mandatory):

- interpret a user request to "push" as explicit approval for `git push --force-with-lease`
- prefer explicit remote/branch in the restated command (example: `git push --force-with-lease origin <branch>`)
- if upstream is missing, `git push --force-with-lease -u <remote> <branch>` is allowed (still requires approval)
- never run `git pull`, `git pull --rebase`, `git rebase <remote>/<branch>`, or `git merge <remote>/<branch>` automatically before pushing
- if push fails due to divergence/non-fast-forward/lease checks, stop and ask for user direction; do not reconcile on your own

Amend policy (mandatory):

- when the user explicitly says "amend", use `git commit --amend`
- do not second-guess amend requests by inspecting the commit author; the git author field reflects git config, not whether the agent created the commit
- if the amended commit was already pushed, the subsequent push will need `--force-with-lease` (covered by push policy above)

Commit quality:

- use Conventional Commits when the repo already uses them; otherwise match the repo's existing commit style
- commit-message style does not transfer to PR titles.
  PR titles are owned by `github` plus any verified domain overlay, not by this commit-quality rule.
- infer `scope` from change surface (best effort)
- each commit must be minimal and atomic, independently reviewable
- commit body bullets are optional; include only when they add signal
- do not invent issue numbers
- do not put `Closes #X` / `Addresses #X` in commit messages; prefer PR description for issue linking
- if the repo uses semantic-release, do not manually version bump unless the repo requires it

Repo/org-specific commit attribution:

- A domain overlay is a repo/org-specific skill selected from the verified repo/org, not guessed from wording.
  It layers repo-specific policy onto this generic git workflow skill.
- If the verified repo/org has an overlay, load that overlay before committing and apply its commit-attribution rules.
- For Elastic org repos, load `~/.agents/skills/elastic-domain/SKILL.md` and append the overlay's required `Co-authored-by` trailer with `git commit --trailer=...`.

Branching:

- follow repo/team branch naming if one exists; otherwise default to `<type>/<scope>/<kebab-description>` (example:
  `chore/opencode/update-sop-wording`)

Merge policy:

- never merge into the base branch via CLI; merges happen via the GitHub UI

Output:

- Summarize repo state, the command(s) run, and the verification result.
- If a requested action would be destructive or cross into another skill's scope, stop and route instead of improvising.
