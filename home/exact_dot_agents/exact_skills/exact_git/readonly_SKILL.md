---
name: git
description: |-
  Local git workflow: branching, committing, pushing, rebasing, merging,
  conflict resolution, and repo safety rules. Use before any local git
  operation. Not for GitHub side effects or worktree management.
---

# Git Workflow Skill

Use this skill for local git repo operations:

- status/diff/log
- staging/unstaging
- branch management
- conflict resolution
- preparing commits

External truth applies:

- verify behavior from the actual repo/version (`git --version`,
  `git help <cmd>`); do not rely on memory.

Do not use:

- GitHub/`gh` operations (PRs, issues, labels, comments, reviews):
  `~/.agents/skills/github/SKILL.md`
- Writing-only PR/issue composition: `~/.agents/skills/compose-pr/SKILL.md`,
  `~/.agents/skills/compose-issue/SKILL.md`
- Worktree management (create/switch/remove worktrees, PR worktrees):
  `~/.agents/skills/worktrees/SKILL.md`

First actions:

1. Establish repo state with the smallest relevant read-only probes
   (`git status`, `git diff`, `git log`, branch name).
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
- if upstream is missing, `git push --force-with-lease -u <remote> <branch>` is
  allowed (still requires approval)
- never run `git pull`, `git pull --rebase`, `git rebase <remote>/<branch>`, or
  `git merge <remote>/<branch>` automatically before pushing
- if push fails due to divergence/non-fast-forward/lease checks, stop and ask
  for user direction; do not reconcile on your own

Commit quality:

- use Conventional Commits when the repo already uses them; otherwise match the
  repo's existing commit style
- infer `scope` from change surface (best effort)
- each commit must be minimal and atomic, independently reviewable
- commit body bullets are optional; include only when they add signal
- do not invent issue numbers
- do not put `Closes #X` / `Addresses #X` in commit messages; prefer PR
  description for issue linking
- if the repo uses semantic-release, do not manually version bump unless the
  repo requires it

Co-author trailer (elastic org repos only):

When the repo belongs to the `elastic` GitHub org, every commit must include a
`Co-authored-by` trailer identifying the AI tool that authored the change.
Append `--trailer` to the `git commit` command.

Known tool identities:

| Tool            | Trailer value                                     |
| --------------- | ------------------------------------------------- |
| Cursor          | `Co-authored-by: Cursor <cursoragent@cursor.com>` |
| Claude Code     | `Co-authored-by: Claude <noreply@anthropic.com>`  |
| Copilot         | `Co-authored-by: Copilot <noreply@github.com>`    |
| OpenCode        | `Co-authored-by: opencode <noreply@opencode.ai>`  |
| pi-coding-agent | `Co-authored-by: pi <noreply@anthropic.com>`      |

- Use the identity row matching the tool you are running inside.
- pi-coding-agent note: pi normally overrides `GIT_AUTHOR_NAME/EMAIL` directly
  (embedding provider + model). If pi handles attribution on its own, skip the
  trailer to avoid duplication. Otherwise use the table row above, replacing the
  email with the active provider's email if known.
- If the current tool is not in the table, ask the user for the correct
  name/email before committing.
- Example:
  `git commit -m "fix: ..." --trailer="Co-authored-by: Cursor <cursoragent@cursor.com>"`

Branching:

- follow repo/team branch naming if one exists; otherwise default to
  `<type>/<scope>/<kebab-description>` (example:
  `chore/opencode/update-sop-wording`)

Merge policy:

- never merge into the base branch via CLI; merges happen via the GitHub UI

Output:

- Summarize repo state, the command(s) run, and the verification result.
- If a requested action would be destructive or cross into another skill's
  scope, stop and route instead of improvising.
