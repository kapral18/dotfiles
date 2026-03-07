# GitHub Issue Body Playbook (Elastic / Kibana)

Use when:

- the user wants an Elastic/Kibana issue body draft only (no `gh` side effects)
- `~/.agents/playbooks/github/gh_workflow.md` needs Elastic-style issue text
  before creating/editing an issue

Scope:

- produces an issue body draft only
- do not create issues via `gh` here; use `~/.agents/playbooks/github/gh_workflow.md` for side effects

Do not use:

- repo is not Elastic/Kibana: `~/.agents/playbooks/github/compose_issue_general.md`
- user wants to create/edit the issue in GitHub: `~/.agents/playbooks/github/gh_workflow.md`

First actions:

1. Verify the repo/context is Elastic/Kibana.
2. Gather reproducible problem, expected behavior, actual behavior, and
   environment details from evidence.
3. Leave unknown stack/deployment/browser fields blank or marked for follow-up;
   do not invent them.

Rules:

- make it reproducible
- include environment details when UI or deployment matters
- redact secrets in logs/screenshots

Output:

- Return only the issue body draft.
- Make missing environment or repro data explicit when it blocks a strong
  issue report.

Template (copy then delete unused sections):

```markdown
## Problem

## Expected

## Actual

## Reproduction

## Environment

- Stack version:
- Deployment (cloud/on-prem):
- Browser/OS (if UI):

## Notes

- Logs / screenshots / sample docs (redact secrets)
- Related issues/PRs
```
