---
name: github-compose-issue-general
description: "Write a GitHub issue body for non-Elastic repos: Problem/Expected/Actual/Reproduction/Notes. Draft-only (no gh side effects). Do NOT use to create/edit issues or post comments."
---

# GitHub Issue Body (General)

Scope:

- This skill produces an issue body draft only.
- Do not create issues via `gh` here; use `~/.agents/skills/github-gh-workflow/SKILL.md` for GitHub side effects.

When NOT to use:

- The repo is Elastic/Kibana: use `~/.agents/skills/github-compose-issue-elastic/SKILL.md`.
- The user wants to create/edit the issue in GitHub: use `~/.agents/skills/github-gh-workflow/SKILL.md`.

Rules:

- Be concrete and reproducible.
- Prefer numbered repro steps.
- Include logs/screenshots only if they add diagnostic value; redact secrets.

Template (copy and then delete unused sections):

```markdown
## Problem

## Expected

## Actual

## Reproduction

## Notes
```
