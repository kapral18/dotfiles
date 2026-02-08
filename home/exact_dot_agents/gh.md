# GitHub + gh Workflow

Defaults & constraints:

- Use `gh` CLI for GitHub activity.
- Follow repository merge settings (squash/rebase/merge); do not enforce a
  merge strategy.
- Never merge into the base branch via CLI; merges happen via the GitHub UI.

Approvals:

- Any GitHub side effect requires explicit approval unless the user instructed
  otherwise (create/edit PRs, comments, reviews, labels, assignees, milestones,
  merges, releases).

PR creation:

- Create PRs as draft by default.
- Always ask which existing issue the PR should reference (do not invent issue
  numbers).
- Ask the user whether the PR should `Closes #X` or `Addresses #X` before
  creating the PR.
- If there is no existing issue, stop and ask whether to create one; do NOT
  create issues unless the user explicitly instructs you to.
- PR title is a human-readable change summary (not necessarily the
  Conventional Commit header).
- Multiline bodies/comments: follow the `$'...'` examples in
  `~/.agents/github_pr_review.md`; do NOT rely on `\\n` escapes inside normal
  quotes when using `gh api -f body=...`.
- Test plan is inferred from the change surface; run the smallest sufficient
  set of checks and record the commands/results in the PR.
- Always propose labels/assignees/milestone/projects first and get explicit
  confirmation before applying any of them.

Template composition guidance:

- ALWAYS open and follow `~/.agents/github_drafting/README.md`.
- Use `~/.agents/github_drafting/general/templates/pr.template.md` /
  `~/.agents/github_drafting/general/templates/issue.template.md` by default.
- For Elastic/Kibana work, choose the closest PR skeleton:
  - Bugfix: `~/.agents/github_drafting/elastic/templates/pr_bugfix.template.md`
  - Chore/migration: `~/.agents/github_drafting/elastic/templates/pr_chore.template.md`
  - Feature: `~/.agents/github_drafting/elastic/templates/pr_feature.template.md`
  - Fallback: `~/.agents/github_drafting/elastic/templates/pr.template.md`
- For Elastic/Kibana issues, use: `~/.agents/github_drafting/elastic/templates/issue.template.md`.
- For Kibana Management-owned areas, consult
  `~/.agents/github_drafting/elastic/team_kibana_management.md` and the repo CODEOWNERS
  to propose `Team:Kibana Management`.
- Do not add/modify repo `.github/*` templates unless the user explicitly asks.

Sub-issues API:

GitHub's sub-issue API creates real parent-child relationships (not tasklists).

Create hierarchy:

1. Create child issues first with full descriptions.
2. Get GraphQL IDs:

```bash
gh api graphql -f query='{ repository(owner:"org",name:"repo") { issue(number:N) { id } } }'
```

3. Link:

```bash
gh api graphql -f query="mutation { addSubIssue(input:{issueId:\"PARENT_ID\",subIssueId:\"CHILD_ID\"}) { issue { number } } }"
```

4. Verify: `gh api repos/:owner/:repo/issues/NUM/sub_issues`

Mutations: `addSubIssue`, `removeSubIssue`, `reprioritizeSubIssue`
