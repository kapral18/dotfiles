---
name: k-git
description: "Use for local git operations: status, diff, log, staging, branches, commits, pushes, rebases, conflicts."
---

# Git Workflow Skill

External truth applies:

- verify behavior from the actual repo/version (`git --version`, `git help <cmd>`); do not rely on memory.

Do not use:

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

- Never print configured remote URLs verbatim.
  Commands such as `git remote -v`, `git remote get-url`, `git config --get remote.*.url`, and broad `git config --list` / `--show-origin` probes may expose credentials embedded as URL userinfo.
- Resolve repository and PR identity with platform metadata (`gh repo view`, `gh pr view`) and list remote names with `git remote`;
  a named remote is sufficient for fetch/push commands.
- Inspect an exact remote URL only when the task materially depends on URL semantics.
  Redact userinfo inside the local command pipeline before any output reaches the model, and return only the redacted value;
  never emit or interpolate the raw URL into model-visible text.
- Redaction is not permission to inspect credential-bearing configuration.
  Prefer a probe that never reads the URL when remote names or platform metadata answer the question.

Safety protocol:

- change git config only when explicitly requested
- run destructive/irreversible commands (hard resets, plain `--force` pushes) only when explicitly requested
- bypass hooks (`--no-verify`, etc.) only when explicitly requested

Approvals:

- Never run `git commit` unless the user explicitly requested a commit in the current conversation.
- Content approval is not commit authorization: "make it generic", "fix it", "do it", or approval of file edits authorizes the edits, not a commit.
- When a task would conventionally end with a commit, stop at the working tree and report the change set;
  the user commits or asks for one explicitly.
- A user-invoked `k-pr-fix-loop` approval packet is an explicit commit request for scoped PR-fix commits on the current PR branch.
- An explicit push request covers committing the changes it describes; absent that, leave the tree uncommitted.
- Do not push without an explicit push request.

Commit and push procedure (mandatory):

Before composing a commit message or running commit, amend, or push commands, MUST load and follow `~/.agents/skills/k-git/references/commit-push.md`.
Do not execute those commands until its push, amend, commit-quality, and attribution rules have been applied.

Branching:

- follow repo/team branch naming if one exists; otherwise default to `<type>/<scope>/<kebab-description>` (example:
  `chore/opencode/update-sop-wording`)

Merge policy:

- never merge into the base branch via CLI; merges happen via the GitHub UI

Output:

- Summarize repo state, the command(s) run, and the verification result.
- If a requested action would be destructive or cross into another skill's scope, stop and route instead of improvising.
