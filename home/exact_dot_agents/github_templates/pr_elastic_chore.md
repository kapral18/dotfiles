# PR Description (Elastic / Kibana) - Chore / Migration / Tech Debt

Use this for migrations, refactors, and technical debt work.

Hard rules:
- The first non-empty line declares issue linkage: `Closes #X` or `Addresses #X`.
- If split into multiple commits, say why and how to review (commit-by-commit guidance).

Template:
```
Closes #X | Addresses #X

## Summary
-

## Review tips
- If this PR is intentionally split into multiple commits, explain the split and the recommended review order.

## What changed (high level)

### Runtime code
-

### Tests
-

## Parity notes
- Any intentional behavior changes vs previous implementation

## Test Plan
- Commands run + key results

## Risk / Rollback
-

## Labels / Meta (agent guidance)

Common label patterns in `elastic/kibana` for chore/migration PRs:
- Type: `chore` or `technical debt` (repo label conventions vary)
- Release notes: usually `release_note:skip`
- Backports: often `backport:skip`
- Team/feature ownership: `Team:*`, `Feature:*`

For Kibana Management-owned areas, `Team:Kibana Management` is common (see CODEOWNERS).

Propose labels; do not apply unless explicitly approved.
```
