# Elastic / Kibana Label Guidance (Propose-Only)

These are common label patterns observed in `elastic/kibana`. Use them as
suggestions only.

Do not add/modify labels unless explicitly approved. Always propose the exact
label set and confirm before applying.

Common patterns:

- Team ownership: `Team:*` (for Kibana Management-owned areas, `Team:Kibana
Management` is common)
- Feature tags: `Feature:<area>` (repo label set varies; verify existing
  labels before proposing)
- Release notes: `release_note:feature` | `release_note:enhancement` |
  `release_note:skip`
  - In `elastic/kibana`, release-note labels are often required by PR checks.
  - Default to `release_note:skip` unless the user confirms a public-facing
    change.
- Backports: `backport` and variants like `backport:skip`,
  `backport:<version>`
- Version targeting: `vX.Y.Z` (repo conventions vary)
- Docs tags: `docs`

When relevant, capture intended release-note behavior explicitly in the PR
body so labels can be applied consistently.
