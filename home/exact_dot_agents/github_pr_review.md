# GitHub PR Review Workflow

Rules:
- Do not implement reviewer suggestions immediately.
- Critically assess, propose changes, and iterate with the user until explicit approval.

Review & investigation steps:
1. Read PR description fully; view screenshots with the `Read` tool.
2. Read all comments; recursively follow linked issues/PRs.
3. Evaluate reviewer-requested changes; ask for clarification if uncertain.
4. Keep PR title/description concise and aligned with established style. Update if scope shifts.

Suggestions (inline):
```
gh api repos/OWNER/REPO/pulls/NUM/comments \
  -f body=$'wdyt about...\n\n```suggestion\ncode\n```' \
  -f commit_id=SHA -f path=FILE -f side=RIGHT -f line=M
```
Add `-f start_line=N` for multi-line.

Sub-issues API:

GitHub's sub-issue API creates real parent-child relationships (not tasklists).

Create hierarchy:
1. Create child issues first with full descriptions.
2. Get GraphQL IDs:
```
gh api graphql -f query='{ repository(owner:"org",name:"repo") { issue(number:N) { id } } }'
```
3. Link:
```
gh api graphql -f query="mutation { addSubIssue(input:{issueId:\"PARENT_ID\",subIssueId:\"CHILD_ID\"}) { issue { number } } }"
```
4. Verify: `gh api repos/:owner/:repo/issues/NUM/sub_issues`

Mutations: `addSubIssue`, `removeSubIssue`, `reprioritizeSubIssue`
