---
name: github-compose-issue-elastic
description: "Write an Elastic/Kibana-style issue body: Problem/Expected/Actual/Reproduction/Environment/Notes with logs/screenshots guidance. Draft-only (no gh side effects). Do NOT use to create/edit issues or post comments."
---

# GitHub Issue Body (Elastic / Kibana)

Scope:

- This skill produces an issue body draft only.
- Do not create issues via `gh` here; use `~/.agents/skills/github-gh-workflow/SKILL.md` for side effects.

When NOT to use:

- The repo is not Elastic/Kibana: use `~/.agents/skills/github-compose-issue-general/SKILL.md`.
- The user wants to create/edit the issue in GitHub: use `~/.agents/skills/github-gh-workflow/SKILL.md`.

Rules:

- Make it reproducible.
- Include environment details when UI or deployment matters.
- Redact secrets in logs/screenshots.

Template (copy and then delete unused sections):

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
