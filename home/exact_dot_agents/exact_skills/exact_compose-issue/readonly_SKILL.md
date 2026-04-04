---
name: compose-issue
description: Draft an issue title and body as text. Use before creating or editing an issue to compose the description. Text only — no gh side effects.
---

# Compose Issue Body

Use when:

- the user wants an issue body draft only (no `gh` side effects)
- `~/.agents/skills/github/SKILL.md` needs issue text before creating/editing an issue

Scope:

- produces an issue body draft only
- do not create issues via `gh` here; use `~/.agents/skills/github/SKILL.md` for GitHub side effects

Do not use:

- user wants to create/edit the issue in GitHub: `~/.agents/skills/github/SKILL.md`

First actions:

1. Identify the problem statement, expected behavior, actual behavior, and reproduction from verified evidence.
2. Keep repro steps concrete and ordered.
3. If logs/screenshots are referenced, include only what materially helps and redact secrets.
4. If the repo is Elastic/Kibana, use the Elastic variant section below.

Rules:

- be concrete and reproducible
- prefer numbered repro steps
- include logs/screenshots only if they add diagnostic value; redact secrets

Output:

- Return only the issue body draft.
- If crucial repro or environment detail is missing, call it out explicitly rather than guessing.

## General template

```markdown
## Problem

## Expected

## Actual

## Reproduction

## Notes
```

## Elastic / Kibana variant

Use when the repo is Elastic/Kibana.

Additional first actions:

1. Verify the repo/context is Elastic/Kibana.
2. Gather reproducible problem, expected behavior, actual behavior, and environment details from evidence.
3. Leave unknown stack/deployment/browser fields blank or marked for follow-up; do not invent them.

Additional rules:

- include environment details when UI or deployment matters

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
