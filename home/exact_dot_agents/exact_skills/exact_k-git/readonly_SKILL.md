---
name: k-git
description: "Use for local git operations: status, diff, log, staging, branches, commits, pushes, rebases, conflicts."
---

# Git Workflow Skill

External truth applies:

- verify behavior from the actual repo/version (`git --version`, `git help <cmd>`) rather than memory.

Route elsewhere for:

- GitHub/`gh` operations (PRs, issues, labels, comments, reviews): `~/.agents/skills/k-github/SKILL.md`
- Writing-only PR/issue composition: `~/.agents/skills/k-compose-pr/SKILL.md`, `~/.agents/skills/k-compose-issue/SKILL.md`
- Worktree management (create/switch/remove worktrees, PR worktrees): `~/.agents/skills/k-worktrees/SKILL.md`

First actions:

1. Establish repo state with the smallest relevant read-only probes (`git status`, `git diff`, `git log`, branch name).
2. Use the actual repo's history/configuration as the source of truth for workflow conventions.
3. Before any commit/push, restate the exact command and apply the approvals/push policy below.

Large-repo probe safety:

- For initial status/diff/routing probes in large repositories, prefer bounded read-only commands:
  - `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false status --short --branch`
  - `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false diff --name-only`
- If a plain `git status`, `git diff`, or branch/upstream probe produces no output after one short wait, stop that command and rerun the bounded form above instead of waiting on the same git process.
- Keep the first probe narrow: status, branch, upstream, changed paths, and the smallest commit range needed for the task.

Remote credential-output safety:

- Keep configured remote URLs out of output; always redact them.
  Commands such as `git remote -v`, `git remote get-url`, `git config --get remote.*.url`, and broad `git config --list` / `--show-origin` probes may expose credentials embedded as URL userinfo.
- Resolve repository and PR identity with platform metadata (`gh repo view`, `gh pr view`) and list remote names with `git remote`;
  a named remote is sufficient for fetch/push commands.
- Inspect an exact remote URL only when the task materially depends on URL semantics.
  Redact userinfo inside the local command pipeline before any output reaches the model, and return only the redacted value;
  only the redacted URL may be emitted or interpolated into model-visible text.
- Redaction is not permission to inspect credential-bearing configuration.
  Prefer a probe that never reads the URL when remote names or platform metadata answer the question.

Safety protocol:

- change git config only when explicitly requested
- run destructive/irreversible commands (hard resets, plain `--force` pushes) only when explicitly requested
- bypass hooks (`--no-verify`, etc.) only when explicitly requested

Approvals:

- Run `git commit` only when the user explicitly requested a commit in the current conversation.
- Content approval is not commit authorization: "make it generic", "fix it", "do it", or approval of file edits authorizes the edits, not a commit.
- When a task would conventionally end with a commit, stop at the working tree and report the change set;
  the user commits or asks for one explicitly.
- An explicit push request covers committing the changes it describes; absent that, leave the tree uncommitted.
- Push only on an explicit push request.

Push policy (mandatory):

- Interpret a user request to "push" as explicit approval for `git push --force-with-lease`.
- Prefer explicit remote/branch in the restated command (example: `git push --force-with-lease origin <branch>`).
- If upstream is missing, `git push --force-with-lease -u <remote> <branch>` is allowed.
- Run `git pull`, `git pull --rebase`, `git rebase <remote>/<branch>`, or `git merge <remote>/<branch>` before pushing only when the user asks for it.
- If push is rejected for divergence, non-fast-forward, lease failure, or diverged history, stop and ask how to proceed.
- Reconcile branch history only when the user explicitly asks for that exact action.

Amend policy (mandatory):

- when the user explicitly says "amend", use `git commit --amend`
- take amend requests at face value; the git author field reflects git config, not whether the agent created the commit
- if the amended commit was already pushed, the subsequent push will need `--force-with-lease` (covered by push policy above)

Commit quality:

- use Conventional Commits when the repo already uses them; otherwise match the repo's existing commit style
- commit-message style does not transfer to PR titles.
  PR titles are owned by `k-github` plus any verified domain overlay, not by this commit-quality rule.
- infer `scope` from change surface (best effort)
- each commit must be minimal and atomic, independently reviewable
- commit body bullets are optional; include only when they add signal
- use only verified issue numbers
- put `Closes #X` / `Addresses #X` in the PR description for issue linking, keeping commit messages free of them
- if the repo uses semantic-release, leave version bumps to it unless the repo requires manual bumps

Repo/org-specific commit attribution:

- A domain overlay is a repo/org-specific skill selected from the verified repo/org, not guessed from wording.
  It layers repo-specific policy onto this generic git workflow skill.
- If the verified repo/org has an overlay, load that overlay before committing and apply its commit-attribution rules.
- For Elastic org repos, load `~/.agents/skills/k-elastic-domain/SKILL.md` and append the overlay's required `Co-authored-by` trailer with `git commit --trailer=...`.

Branching:

- follow repo/team branch naming if one exists; otherwise default to `<type>/<scope>/<kebab-description>` (example:
  `chore/opencode/update-sop-wording`)

Merge policy:

- merge into the base branch only via the GitHub UI, never via CLI

Output:

- Summarize repo state, the command(s) run, and the verification result.
- If a requested action would be destructive or cross into another skill's scope, stop and route instead of improvising.
