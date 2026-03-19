---
name: compose-pr
description: |-
  Draft a PR title and body as text. Use before creating or editing a PR
  to compose the description. Text only — no gh side effects.
---

# Compose PR Body

Use when:

- the user wants a PR body draft only (no `gh` side effects)
- `~/.agents/skills/github/SKILL.md` needs a draft body before creating/editing
  a PR

Scope:

- produces a PR body draft only
- do not run `gh` or change PR metadata; use `~/.agents/skills/github/SKILL.md`
  for side effects

Do not use:

- user wants to create/edit PR in GitHub: `~/.agents/skills/github/SKILL.md`
- user is asking for PR review feedback: `~/.agents/skills/review/SKILL.md`

First actions:

1. Inspect the current diff/branch context and the user-supplied issue refs.
2. Extract only evidence you can verify (summary, test plan, migration notes).
3. If issue linkage or test evidence is missing, keep placeholders instead of
   inventing details.
4. If the repo is Elastic/Kibana, use the Elastic variant section below.

Rules:

- keep it short and reviewable
- prefer bullets over prose
- test plan must be evidence: commands run + observed result
- link issues explicitly:
  - `Closes #X` only when merging should close the issue
  - `Addresses #X` when it should not auto-close
  - never invent issue numbers

Output:

- Return only the PR body draft, ready to paste or hand to
  `~/.agents/skills/github/SKILL.md`.
- If important inputs are missing, say exactly which placeholders still need
  confirmation.

## General template

```markdown
Closes #X | Addresses #X

## Summary

-

## Test Plan

-
```

## Elastic / Kibana variant

Use when the repo is Elastic/Kibana.

Additional first actions:

1. Verify the repo/context is Elastic/Kibana.
2. Gather only verified evidence for summary, root cause/fix, test plan, and
   release-note intent.
3. If the user also asks for label/reviewer guidance, load the Kibana label
   and/or ownership skills before finalizing the draft.

Additional rules:

- make release note intent explicit (even if labels are applied later)
- never invent issue numbers; use `Closes #X` vs `Addresses #X` intentionally

Optional guidance:

- label proposals (propose-only): `~/.agents/skills/labels_propose/SKILL.md`
- Kibana Management ownership signals:
  `~/.agents/skills/kibana-management-ownership/SKILL.md`

Default template (copy then delete unused sections):

```markdown
Closes #X | Addresses #X

## Summary

-

## Test Plan
```

Bugfix:

```markdown
Closes #X | Addresses #X

## Summary

-

## Root Cause

-

## Fix

-

## Before/After Screenshots (or Video)

### Before

### After

## Test Plan

-

## Release Note

- Single sentence describing user-facing behavior change (or lack thereof, if
  `skip`).
```

Chore/Migration:

```markdown
Closes #X | Addresses #X

## Summary

-

## Rationale

-

## Test Plan
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

## Release Note

- Single sentence describing user-facing behavior change (or lack thereof, if
  `skip`).
```
