# GitHub Issue Creation Reference

Load before `gh issue create` or issue body/title edits.

## Required composition packet

- Before creating/editing an issue body, invoke `k-compose-issue`.
- Before `gh issue create` or issue body/title edit, require the `k-compose-issue` issue publication packet.
- Stop if the packet is missing, any required field is missing, or any required field is `blocked`.
- If the repo supports GitHub issue types, the packet must include `issue_type` with an exact GitHub issue type;
  labels do not satisfy this gate.

## Issue type gate

- Before `gh issue create`, verify local CLI support with `GH_PAGER=cat gh issue create --help`.
- If `--type name` is absent, stop unless the approved packet explicitly allows creation without a GitHub issue type.
- For repos exposing issue types, read allowed names first:

```bash
GH_PAGER=cat gh api graphql -H "GraphQL-Features:issue_types" -f query='query { repository(owner:"OWNER", name:"REPO") { issueTypes(first: 50) { nodes { id name description } } } }'
```

- Use `gh issue create --type <IssueType> --body-file <file>` when approved.
- If setting the approved issue type fails, stop and ask; do not silently fall back to labels-only creation.

## Preflight ledger

Before `gh issue create`, show:

- `target`: repo, visibility if relevant, creation/edit intent
- `title`: exact title plus source/rationale
- `body`: body file/path or full text source, sanitization status
- `issue_type`: exact GitHub issue type, source evidence, approval status
- `metadata`: labels, assignees, milestone, projects plus source/rationale and approval status
- `relationships`: parent issue/sub-issue links, linked issues/PRs, approval status
- `duplicate_check`: queries run, hits read, duplicate verdict
- `intake`: full references read; skipped references with reasons
- `approval`: exact side effect command/payload approved by the user, including `--type <IssueType>` and relationship mutations

## Readback

After create/edit, read back title, body, labels, assignees, milestone, projects, and issue type via GraphQL when applicable:

```bash
GH_PAGER=cat gh api graphql -H "GraphQL-Features:issue_types" -f query='query { repository(owner:"OWNER", name:"REPO") { issue(number: NUMBER) { issueType { name } } } }'
```

Compare each field against the approved preflight ledger; fix or get explicit acceptance for mismatches.
If parent/sub-issue links were approved, apply them through `k-github/references/sub-issues.md`, then read back the relationship.
