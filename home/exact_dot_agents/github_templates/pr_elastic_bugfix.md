# PR Description (Elastic / Kibana) - Bugfix

Use this for bugfixes where demonstrating the fix matters.

Hard rules:
- The first non-empty line declares issue linkage: `Closes #X` or `Addresses #X`.
- Include a clear Before/After section (screenshots, GIFs, or short video link) when the bug is user-facing.

Template:
```
Closes #X | Addresses #X

## Summary
- What broke
- What this changes

## DEMO (Before / After)
- Link to recording / screenshots

## Root cause
-

## Fix
-

## Tests
- What you added/updated and why

## Test Plan
- Commands run + key results

## Risk / Rollback
-

## Labels / Meta (agent guidance)

Common label patterns in `elastic/kibana` for bugfix PRs:
- Type: `bug`
- Release notes: `release_note:skip` is common for internal fixes; otherwise consider `release_note:enhancement`
- Backports: often `backport:*` (repo-specific policy)
- Team/feature ownership: `Team:*`, `Feature:*`

For Kibana Management-owned areas, `Team:Kibana Management` is common (see CODEOWNERS).

Propose labels; do not apply unless explicitly approved.
```
