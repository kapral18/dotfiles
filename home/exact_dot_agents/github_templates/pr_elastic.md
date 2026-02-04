# PR Description (Elastic / Kibana / Elasticsearch)

Use this when the work touches Elastic Stack codebases and no more specific Elastic PR template applies.

For common Elastic/Kibana PR shapes, prefer:
- `pr_elastic_bugfix.md`
- `pr_elastic_chore.md`
- `pr_elastic_feature.md`

Hard rules:

- The first non-empty line declares issue linkage: `Closes #X` or `Addresses #X`.
- Keep it high-signal and reviewable.

Template:

```
Closes #X | Addresses #X

## Summary
-

## Test Plan
-

## Risk / Rollback
-

## Notes
- Impacted areas (Kibana app, API, ES query, saved objects, UI)
- Migration / BWC considerations (if any)
- Performance considerations (if any)

## Labels / Meta (agent guidance)

These are common label patterns observed in `elastic/kibana`. Use them when they fit, but do not add/modify labels unless explicitly approved.

- Team ownership: `Team:Kibana Management`
- Feature tags: `Feature:<area>` (e.g., `Feature:Console`, `Feature:ILM` etc...) (check existing labels via gh cli for reference)
- Release notes: `release_note:feature` | `release_note:enhancement` | `release_note:skip` (it's a required label that fails PR gate if missing, should be skip by default unless public faciing or api changes are made in which case ask for the user)
- Backports: `backport` and variants like `backport:skip`, `backport:version` ( backport:all-open for bugfixes)
- Version targeting: `v9.4.0` (and similar)
- Docs tags: `docs`

When relevant, capture the intended release-note behavior explicitly in the PR description (in Summary or Notes) so labels can be applied consistently.
```
