---
name: github-compose-pr-general
description: "Write a GitHub pull request body for non-Elastic repos: concise Summary + Test Plan, correct issue linking language, and remove irrelevant sections. Draft-only (no gh side effects). Do NOT use to create/edit PRs or post comments."
---

# GitHub PR Body (General)

Scope:

- This skill produces a PR body draft only.
- Do not run `gh` or change PR metadata; use `~/.agents/skills/github-gh-workflow/SKILL.md` for that.

When NOT to use:

- The user wants to create/edit the PR in GitHub: use `~/.agents/skills/github-gh-workflow/SKILL.md`.
- The repo is Elastic/Kibana and you want the Elastic-style sections: use `~/.agents/skills/github-compose-pr-elastic/SKILL.md`.
- The user is asking for PR review feedback: use the `github-pr-review-*` skills.

Rules:

- Keep it short and reviewable.
- Prefer bullets over prose.
- Test Plan must be evidence: commands run + observed result.
- Link issues explicitly:
  - `Closes #X` only when merging the PR should close the issue.
  - `Addresses #X` when it should not auto-close.
  - Never invent issue numbers.

Template (copy and then delete unused sections):

```markdown
Closes #X | Addresses #X

## Summary

- 

## Test Plan

- 
```
