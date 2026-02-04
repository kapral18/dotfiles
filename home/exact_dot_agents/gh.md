# GitHub + gh Workflow

Defaults & constraints:
- Use `gh` CLI for GitHub activity.
- Follow repository merge settings (squash/rebase/merge); do not enforce a merge strategy.
- Never merge into the base branch via CLI; merges happen via the GitHub UI.

Approvals:
- Any GitHub side effect requires explicit approval unless the user instructed otherwise (create/edit PRs, comments, reviews, labels, assignees, milestones, merges, releases).

PR creation:
- Create PRs as draft by default.
- Ask the user whether the PR should `Closes #X` or `Addresses #X` before creating the PR.
- PR title is a human-readable change summary (not necessarily the Conventional Commit header).
- Test plan is inferred from the change surface; run the smallest sufficient set of checks and record the commands/results in the PR.

Template composition guidance:
- ALWAYS open and follow `~/.agents/github_templates/README.md`.
- Use `~/.agents/github_templates/pr_base.md` / `~/.agents/github_templates/issue_base.md` by default.
- For Elastic/Kibana work, choose the closest PR flavor:
  - Bugfix: `~/.agents/github_templates/pr_elastic_bugfix.md`
  - Chore/migration: `~/.agents/github_templates/pr_elastic_chore.md`
  - Feature: `~/.agents/github_templates/pr_elastic_feature.md`
  - Fallback: `~/.agents/github_templates/pr_elastic.md`
- For Kibana Management-owned areas, consult `~/.agents/github_templates/team_kibana_management.md` and the repo CODEOWNERS to propose `Team:Kibana Management`.
- Do not add/modify repo `.github/*` templates unless the user explicitly asks.
