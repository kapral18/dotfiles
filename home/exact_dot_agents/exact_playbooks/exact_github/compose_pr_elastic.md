# GitHub PR Body Playbook (Elastic / Kibana)

Scope:

- produces a PR body draft only
- do not run `gh` or apply labels here; use `~/.agents/playbooks/github/gh_workflow.md` for side effects

When NOT to use:

- repo is not Elastic/Kibana: `~/.agents/playbooks/github/compose_pr_general.md`
- user wants to create/edit PR in GitHub: `~/.agents/playbooks/github/gh_workflow.md`
- user is asking for PR review feedback: `~/.agents/playbooks/review/router.md`

Rules:

- keep it short; default to bullets
- make release note intent explicit (even if labels are applied later)
- test plan must be evidence: commands run + observed result
- never invent issue numbers; use `Closes #X` vs `Addresses #X` intentionally

Optional guidance:

- label proposals (propose-only): `~/.agents/playbooks/github/labels_propose_elastic_kibana.md`
- Kibana Management ownership signals: `~/.agents/playbooks/kibana/management_ownership.md`

Default template (copy then delete unused sections):

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

Variants:

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
