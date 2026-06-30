---
name: kibana-labels-propose
description: "Use when proposing elastic/kibana PR/issue labels, backports, or version targets, including while drafting or after creating a Kibana PR; propose-only."
---

# Elastic / Kibana Label Guidance (Propose-Only)

Use when:

- the direct ask is "what labels/backports/version targeting should this `elastic/kibana` PR/issue get?"
- drafting/composing an `elastic/kibana` PR description (even if the user didn’t explicitly say “labels”) and you want to include a verified proposed label set
- immediately after creating an `elastic/kibana` PR (given a PR URL/number), to propose the labels/backport/version targeting that should be applied

Non-negotiables:

- propose only; never apply labels unless explicitly approved
- verify labels exist in the target repo; do not propose from memory if you cannot verify the label set
- this skill is the source of truth for `elastic/kibana` label/backport/version classification;
  other skills may route here but should not independently infer labels

Do not use:

- repo is not `elastic/kibana` (or label set cannot be verified)
- user asked to apply labels now:
  - use `~/.agents/skills/github/SKILL.md` (still requires explicit approval)

First actions:

1. Verify the target repo is `elastic/kibana`.
2. Read the current repo label set before proposing anything.
3. Read the label-relevant signals — the changed file paths/ownership plus the PR/issue body, closing/resolved issue, directly linked issues, and their labels, enough to judge release-note and backport intent.
   Labels are a bounded classification; a full recursive crawl of every comment/thread is not required.
   Skim the discussion only if the body leaves release-note or backport intent genuinely ambiguous.
4. Map the change/issue to exact proposed labels, then separate verified labels from heuristics.

Output:

- Return the exact proposed label set and a short rationale for each non-obvious label.
- If a label cannot be verified in the repo, say so and do not propose it as a fact.

Common patterns (verify in repo):

- review routing (required on every PR): always include both `reviewer:codex` and `reviewer:claude` in the proposed label set.
  These are mandatory on each composed `elastic/kibana` PR; do not drop them.
- team ownership: `Team:*`
- resolved/linked issue labels:
  - use the issue that the PR closes/addresses as a primary classification signal, especially for `Team:*`, `Feature:*`, `bug`, and similar area/type labels
  - do not blindly copy every issue label to the PR; drop issue-only workflow labels or labels contradicted by the PR's changed paths/scope
  - when issue labels and changed paths disagree, treat that as a fork: explain the conflict and ask or mark the extra label as heuristic instead of applying it as fact
- feature tags: `Feature:<area>` (varies)
  - prefer the owning plugin/area from changed paths and the directly linked issue's existing feature labels
  - do not add a cross-feature label only because the PR body mentions that feature or shared technology
  - when all changed paths and the linked issue point to Console, propose `Feature:Console`;
    do not add `Feature:ES|QL` unless there is separate evidence that the ES|QL feature area owns/reviews the change
  - mark any additional feature label as heuristic with a short rationale, and leave it out if that rationale is not evidence-backed
- release notes: `release_note:feature` | `release_note:enhancement` | `release_note:fix` | `release_note:skip`
  - default to `release_note:skip` unless user confirms public-facing change
  - include a `## Release Note` section in the PR body only when the label is `release_note:fix` or `release_note:feature`;
    omit the section entirely for all other release note labels
- backports:
  - `backport:skip` (default if no backport is needed) (no version tag if skipping)
  - `backport:all-open` (backport to all open minor versions) (no version tag)
  - `backport:version` + `vX.Y.Z` (backport to a specific version) (version tag required)
- docs tags: `docs`
