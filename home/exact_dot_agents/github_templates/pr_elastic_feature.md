# PR Description (Elastic / Kibana) - Feature

Use this for user-facing features, especially UI-heavy work.

Hard rules:
- The first non-empty line declares issue linkage: `Closes #X` or `Addresses #X`.
- Include a UI Changes section (Before/After) when applicable.
- Break down into clearly reviewable chunks.

Template:
```
Closes #X | Addresses #X

## Summary
-

## UX / UI Changes (Before / After)
- Screenshots / recordings

## Behavior
- What’s new
- What’s unchanged
- Edge cases

## Test Plan
- Commands run + key results
- Manual verification steps (if UI)

## Risk / Rollback
-

## Notes
- Migration / BWC considerations (if any)
- Performance considerations (if any)

## Labels / Meta (agent guidance)

Common label patterns in `elastic/kibana` for feature PRs:
- Release notes: often `release_note:feature`
- Team/feature ownership: `Team:*`, `Feature:*`
- CI labels may be used by the repo (e.g., `ci:*` in some areas)
- Versions may be tagged (e.g., `v9.0.0`, `v8.16.0`)

Propose labels; do not apply unless explicitly approved.

For Kibana Management-owned areas, `Team:Kibana Management` is common (see CODEOWNERS).
```
