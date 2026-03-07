# GitHub Issue Body Playbook (General)

Use when:

- the user wants an issue body draft only (no `gh` side effects)
- `~/.agents/playbooks/github/gh_workflow.md` needs issue text before
  creating/editing an issue

Scope:

- produces an issue body draft only
- do not create issues via `gh` here; use `~/.agents/playbooks/github/gh_workflow.md` for GitHub side effects

Do not use:

- repo is Elastic/Kibana: `~/.agents/playbooks/github/compose_issue_elastic.md`
- user wants to create/edit the issue in GitHub: `~/.agents/playbooks/github/gh_workflow.md`

First actions:

1. Identify the problem statement, expected behavior, actual behavior, and
   reproduction from verified evidence.
2. Keep repro steps concrete and ordered.
3. If logs/screenshots are referenced, include only what materially helps and
   redact secrets.

Rules:

- be concrete and reproducible
- prefer numbered repro steps
- include logs/screenshots only if they add diagnostic value; redact secrets

Output:

- Return only the issue body draft.
- If crucial repro or environment detail is missing, call it out explicitly
  rather than guessing.

Template (copy then delete unused sections):

```markdown
## Problem

## Expected

## Actual

## Reproduction

## Notes
```
