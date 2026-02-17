# GitHub Issue Body Playbook (General)

Scope:

- produces an issue body draft only
- do not create issues via `gh` here; use `~/.agents/playbooks/github/gh_workflow.md` for GitHub side effects

When NOT to use:

- repo is Elastic/Kibana: `~/.agents/playbooks/github/compose_issue_elastic.md`
- user wants to create/edit the issue in GitHub: `~/.agents/playbooks/github/gh_workflow.md`

Rules:

- be concrete and reproducible
- prefer numbered repro steps
- include logs/screenshots only if they add diagnostic value; redact secrets

Template (copy then delete unused sections):

```markdown
## Problem

## Expected

## Actual

## Reproduction

## Notes
```
