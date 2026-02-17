# GitHub Issue Body Playbook (Elastic / Kibana)

Scope:

- produces an issue body draft only
- do not create issues via `gh` here; use `~/.agents/playbooks/github/gh_workflow.md` for side effects

When NOT to use:

- repo is not Elastic/Kibana: `~/.agents/playbooks/github/compose_issue_general.md`
- user wants to create/edit the issue in GitHub: `~/.agents/playbooks/github/gh_workflow.md`

Rules:

- make it reproducible
- include environment details when UI or deployment matters
- redact secrets in logs/screenshots

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
