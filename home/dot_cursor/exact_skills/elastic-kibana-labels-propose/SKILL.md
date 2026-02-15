---
name: elastic-kibana-labels-propose
description: "Propose-only label guidance for Elastic/Kibana PRs: Team:* ownership, Feature:*, release_note labels, backports, version targeting, docs. Use when deciding label sets for elastic/kibana; never apply without explicit approval. Do NOT use for non-Elastic/Kibana repos or for applying labels."
---

# Elastic / Kibana Label Guidance (Propose-Only)

These are common label patterns observed in `elastic/kibana`. Use them as
suggestions only.

Do not add/modify labels unless explicitly approved. Always propose the exact
label set and confirm before applying.

When NOT to use:

- The repo is not `elastic/kibana` (or you cannot verify the label set exists): do not propose from memory.
- The user asked you to apply labels now: use `~/.agents/skills/github-gh-workflow/SKILL.md` (still requires explicit approval).

Common patterns:

- Team ownership: `Team:*` (for Kibana Management-owned areas, `Team:Kibana Management` is common)
- Feature tags: `Feature:<area>` (repo label set varies; verify existing labels before proposing)
- Release notes: `release_note:feature` | `release_note:enhancement` | `release_note:skip`
  - In `elastic/kibana`, release-note labels are often required by PR checks.
  - Default to `release_note:skip` unless the user confirms a public-facing change.
- Backports: `backport` and variants like `backport:skip`, `backport:<version>`
- Version targeting: `vX.Y.Z` (repo conventions vary)
- Docs tags: `docs`

When relevant, capture intended release-note behavior explicitly in the PR body
so labels can be applied consistently.
