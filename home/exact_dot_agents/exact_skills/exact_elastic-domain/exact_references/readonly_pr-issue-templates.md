# Elastic/Kibana PR and Issue Body Templates

Reference for the `elastic-domain` skill. Load when drafting an `elastic/kibana` PR or issue body and a copy-paste template is needed.
Policy (footer placement, release-note inclusion rule, title-bracket rule, issue-body field rules) lives in the core `SKILL.md`, not here —
this file is templates only.

## PR template: Default (copy then delete unused sections)

```markdown
Closes #X | Addresses #X

## Summary

-

## Test Plan

Assisted with <Tool> using <Model>
```

## PR template: Bugfix

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

- Single sentence describing the user-facing behavior change.

Assisted with <Tool> using <Model>
```

## PR template: Chore/Migration

```markdown
Closes #X | Addresses #X

## Summary

-

## Rationale

-

## Test Plan

Assisted with <Tool> using <Model>
```

## PR template: Feature

```markdown
Closes #X | Addresses #X

## Summary

-

## User-Facing Behavior

-

## Test Plan

-

## Release Note

- Single sentence describing the user-facing behavior change.

Assisted with <Tool> using <Model>
```

## Issue template: Kibana (copy and delete unused sections)

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
