---
name: git-workflow
description: "Local git repository operations: status/diff/log, staging, branch management, conflict resolution, and preparing commits. Use when the user asks for git commands or mentions commit/push/branch/rebase/merge. Requires explicit approval before running git commit or git push; follow the safety protocol in the canonical git SOP. Do NOT use for GitHub/gh PR/issue operations."
---

# Git Workflow

External truth applies: verify behavior from the actual repo/version (use `git
--version`, `git help <cmd>`). Do not rely on memory.

When NOT to use:

- GitHub/gh operations (PRs, issues, labels, comments, reviews): use `~/.agents/skills/github-gh-workflow/SKILL.md`.
- Writing-only PR/issue composition: use the `github-compose-*` skills.
- Worktree management (create/switch/remove worktrees, PR worktrees): use `~/.agents/skills/w-workflow/SKILL.md`.

Safety protocol:

- Never change git config unless explicitly requested.
- Never run destructive/irreversible git commands (e.g., hard resets, force
  pushes) unless explicitly requested.
- Never bypass hooks (`--no-verify`, etc.) unless explicitly requested.

Approvals:

- Always get explicit approval before `git commit`.
- Always get explicit approval before `git push`.

Commit quality:

- Use Conventional Commits.
- Infer `scope` from change surface (best effort).
- Each commit must be minimal and atomic, and should be independently
  reviewable.
- Commit body bullets are optional; include only when they add signal.
- Do not put `Closes #X` / `Addresses #X` in commit messages (use PR
  description).
- semantic-release handles versioning; do not manually version bump unless the
  repo requires it.

Branching:

- Branch name: `<type>/<scope>/<kebab-description>` (e.g.,
  `chore/opencode/update-sop-wording`).
- If upstream is missing, it is OK to set it with `git push -u` (still
  requires approval).

Merge policy:

- Never merge into the base branch via CLI; merges happen via the GitHub UI.
