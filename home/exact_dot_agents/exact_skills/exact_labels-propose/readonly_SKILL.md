---
name: labels-propose
description: |-
  Use when the user wants suggested labels/backports/version targeting for
  elastic/kibana (no posting). Propose exact verified labels only; applying
  labels routes to GitHub side effects.
---

# Elastic / Kibana Label Guidance (Propose-Only)

Use when:

- the direct ask is "what labels/backports/version targeting should this
  `elastic/kibana` PR/issue get?"
- a loaded Elastic compose/GitHub playbook needs verified Kibana label proposals

These are common label patterns observed in `elastic/kibana`. Use them as
suggestions only.

Non-negotiables:

- propose only; never apply labels unless explicitly approved
- always propose the exact label set and confirm before applying
- verify labels exist in the target repo; do not propose from memory if you
  cannot verify the label set

Do not use:

- repo is not `elastic/kibana` (or label set cannot be verified)
- user asked to apply labels now:
  - use `~/.agents/playbooks/github/PLAYBOOK.md` (still requires explicit
    approval)

First actions:

1. Verify the target repo is `elastic/kibana`.
2. Read the current repo label set before proposing anything.
3. Map the change/issue to exact proposed labels, then separate verified labels
   from heuristics.

Output:

- Return the exact proposed label set and a short rationale for each non-obvious
  label.
- If a label cannot be verified in the repo, say so and do not propose it as a
  fact.

Common patterns (verify in repo):

- team ownership: `Team:*` (for management-owned areas, `Team:Kibana Management`
  is common)
- feature tags: `Feature:<area>` (varies)
- release notes: `release_note:feature` | `release_note:enhancement` |
  `release_note:fix` | `release_note:skip`
  - often required by PR checks
  - default to `release_note:skip` unless user confirms public-facing change
- backports:
  - `backport:skip` (default if no backport is needed) (no version tag if
    skipping)
  - `backport:all-open` (backport to all open minor versions) (no version tag)
  - `backport:version` + `vX.Y.Z` (backport to a specific version) (version tag
    required)
- docs tags: `docs`

When relevant, capture intended release-note behavior explicitly in the PR body
so labels can be applied consistently.
