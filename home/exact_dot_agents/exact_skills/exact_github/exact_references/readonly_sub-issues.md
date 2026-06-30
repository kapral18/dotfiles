# GitHub Sub-Issues API

Reference for the `github` skill. Load when creating or managing real parent-child issue hierarchies.

GitHub's sub-issue API creates real parent-child relationships (not tasklists).

## Create hierarchy

1. Create child issues first with full descriptions.
2. Get GraphQL IDs:

```bash
gh api graphql -f query='{ repository(owner:"org",name:"repo") { issue(number:N) { id } } }'
```

1. Link:

```bash
gh api graphql -f query="mutation { addSubIssue(input:{issueId:\"PARENT_ID\",subIssueId:\"CHILD_ID\"}) { issue { number } } }"
```

1. Verify: `gh api repos/:owner/:repo/issues/NUM/sub_issues`

Mutations: `addSubIssue`, `removeSubIssue`, `reprioritizeSubIssue`
