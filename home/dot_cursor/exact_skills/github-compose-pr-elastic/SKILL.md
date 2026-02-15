---
name: github-compose-pr-elastic
description: "Write an Elastic/Kibana-style PR body: Summary + Test Plan + Notes (impacted areas, migration, perf, release note intent). Draft-only (no gh side effects). Do NOT use to create/edit PRs or post comments."
---

# GitHub PR Body (Elastic / Kibana)

Scope:

- This skill produces a PR body draft only.
- Do not run `gh` or apply labels here; use `~/.agents/skills/github-gh-workflow/SKILL.md` for GitHub side effects.

When NOT to use:

- The repo is not Elastic/Kibana: use `~/.agents/skills/github-compose-pr-general/SKILL.md`.
- The user wants to create/edit the PR in GitHub: use `~/.agents/skills/github-gh-workflow/SKILL.md`.
- The user is asking for PR review feedback: use the `github-pr-review-*` skills.

Rules:

- Keep it short; default to bullets.
- Make release note intent explicit (even if labels are applied later).
- Test Plan must be evidence: commands run + observed result.
- Never invent issue numbers; use `Closes #X` vs `Addresses #X` intentionally.

Optional guidance:

- Label proposals (propose-only): see `~/.agents/skills/elastic-kibana-labels-propose/SKILL.md`.
- Kibana Management ownership signals: see `~/.agents/skills/kibana-management-ownership/SKILL.md`.

Default template (copy and then delete unused sections):

```markdown
Closes #X | Addresses #X

## Summary

- 

## Test Plan

- 

## Notes

- Impacted areas (Kibana app, API, ES query, saved objects, UI):
- Migration considerations (if any):
- Performance considerations (if any):
- Release note intent: skip | enhancement | feature
```

Variants (use when it helps clarity):

Bugfix:

```markdown
Closes #X | Addresses #X

## Summary

- 

## Root Cause

- 

## Fix

- 

## Test Plan

- 

## Notes

- Impacted areas:
- Migration considerations (if any):
- Performance considerations (if any):
- Release note intent:
```

Chore/Migration:

```markdown
Closes #X | Addresses #X

## Summary

- 

## Rationale

- 

## Test Plan

- 

## Notes

- Impacted areas:
- Migration considerations (if any):
- Performance considerations (if any):
- Release note intent:
```

Feature:

```markdown
Closes #X | Addresses #X

## Summary

- 

## User-Facing Behavior

- 

## Test Plan

- 

## Notes

- Impacted areas:
- Migration considerations (if any):
- Performance considerations (if any):
- Release note intent:
```
