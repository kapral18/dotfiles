---
name: kibana-labels-propose
description: |-
  Propose labels/backports/version targeting for `elastic/kibana` (propose-only;
  no posting). Use when: drafting/composing an `elastic/kibana` PR description, immediately
  after creating an `elastic/kibana` PR (given PR URL/number), or when asked
  what labels/backports/version targeting a Kibana PR/issue should get.
---

# Elastic / Kibana Label Guidance (Propose-Only)

Use when:

- the direct ask is "what labels/backports/version targeting should this
  `elastic/kibana` PR/issue get?"
- drafting/composing an `elastic/kibana` PR description (even if the user didn’t
  explicitly say “labels”) and you want to include a verified proposed label set
- immediately after creating an `elastic/kibana` PR (given a PR URL/number), to
  propose the labels/backport/version targeting that should be applied

Non-negotiables:

- propose only; never apply labels unless explicitly approved
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

- team ownership: `Team:*`
- feature tags: `Feature:<area>` (varies)
- release notes: `release_note:feature` | `release_note:enhancement` |
  `release_note:fix` | `release_note:skip`
  - default to `release_note:skip` unless user confirms public-facing change
- backports:
  - `backport:skip` (default if no backport is needed) (no version tag if
    skipping)
  - `backport:all-open` (backport to all open minor versions) (no version tag)
  - `backport:version` + `vX.Y.Z` (backport to a specific version) (version tag
    required)
- docs tags: `docs`
