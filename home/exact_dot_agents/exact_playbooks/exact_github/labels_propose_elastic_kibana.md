# Elastic / Kibana Label Guidance (Propose-Only)

Use this playbook when deciding label sets for `elastic/kibana` PRs/issues.

These are common label patterns observed in `elastic/kibana`. Use them as
suggestions only.

Non-negotiables:

- propose only; never apply labels unless explicitly approved
- always propose the exact label set and confirm before applying
- verify labels exist in the target repo; do not propose from memory if you cannot verify the label set

When NOT to use:

- repo is not `elastic/kibana` (or label set cannot be verified)
- user asked to apply labels now:
  - use `~/.agents/playbooks/github/gh_workflow.md` (still requires explicit approval)

Common patterns (verify in repo):

- team ownership: `Team:*` (for management-owned areas, `Team:Kibana Management` is common)
- feature tags: `Feature:<area>` (varies)
- release notes: `release_note:feature` | `release_note:enhancement` | `release_note:skip`
  - often required by PR checks
  - default to `release_note:skip` unless user confirms public-facing change
- backports: `backport`, `backport:skip`, `backport:<version>` (varies)
- version targeting: `vX.Y.Z` (varies)
- docs tags: `docs`

When relevant, capture intended release-note behavior explicitly in the PR body so labels can be applied consistently.
