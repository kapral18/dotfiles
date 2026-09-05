---
name: k-elastic-domain
description: "Use when target is Elastic org, elastic/kibana, Buildkite, ownership, live UI, or domain policy."
---

# Elastic Domain Overlay

This is a domain overlay: it adds Elastic/Kibana policy to a primary generic skill; it does not replace that skill.

Use when:

- current repo/target belongs to the `elastic` GitHub org
- current repo is `elastic/kibana`
- another skill says to load this overlay
- handling Elastic Buildkite, SCSI, Kibana labels, ownership, live UI, Dev Tools Console, or domain policy

Do not use standalone for review, GitHub, git, compose, posting, labeling, resolving, committing, pushing, or mutation.
Outside Elastic/Kibana contexts, use only when explicitly requested.

## Detection

Verify domain evidence before applying rules:

- GitHub target: `gh repo view --json nameWithOwner --jq .nameWithOwner`
- local fallback: `git remote -v` with an `elastic/<repo>` remote
- Kibana-specific behavior applies only for exactly `elastic/kibana`

If detection is unavailable, keep generic behavior and state Elastic-specific rules could not be verified.

## Layering contract

1. Follow the primary skill's generic workflow.
2. Apply the relevant domain additions below before the generic step they govern.
3. Do not duplicate generic mechanics: routing, PR intake, pending-review reconciliation, publication gates, and review judging stay with primary skills.
4. If this overlay conflicts with the primary skill, safer/gated behavior wins.

## GitHub and PR composition

Apply with `k-compose-pr`, `k-compose-issue`, `k-github`, or review flows preparing GitHub-visible text.
Before preparing that text or its domain metadata, read and follow `~/.agents/skills/k-elastic-domain/references/github-composition.md` in full.

## Kibana planning fork checklist

Apply with `k-spec` or any SOP §3.1 intent loop when the verified repo is `elastic/kibana`.
Read `~/.agents/skills/k-elastic-domain/references/kibana-planning-forks.md` to seed forks:
API versioning, Saved Objects/migrations, privileges, dependencies, feature flags, backports, test placement, alerting, instrumentation.
Evidence-first: answer from issue/diff/codebase before asking; only genuine gaps become fork-closing questions.

## Review and CI additions

- Buildkite URLs for Elastic repos go through `k-buildkite` and `bk`; do not fetch `buildkite.com` directly.
- For `k-present-pr`, fetch only compact Buildkite facts needed for the story:
  build number, state, commit, and current-vs-historical failures.
- Labels/backports/version targeting are propose-only through `k-kibana-labels-propose` unless the user approves GitHub mutation.
- Ownership/reviewer targeting is propose-only through `k-kibana-management-ownership`; side effects go through `k-github` after approval.
- When the review Signal-Quality Gate triggers on Elastic observability surfaces, this overlay owns query/product specifics:
  ES|QL / Query DSL must match target stack syntax/semantics; fields must match mapping types; aggregation buckets must fit expected volume;
  flag timeout/OOM-prone queries.
- Known Elastic bot logins: `elasticmachine`, `kibanamachine`, `github-actions[bot]`.

## Git commit attribution

Before preparing or creating an Elastic commit, read and follow `~/.agents/skills/k-elastic-domain/references/commit-attribution.md` in full for required tool attribution and its exceptions.

## Live UI overlay

For `elastic/kibana` live UI verification, load:

```text
~/.agents/skills/k-elastic-domain/references/kibana-live-ui.md
~/.agents/skills/k-elastic-domain/references/kibana-live-ui-evidence.md
```

The first reference owns Kibana runtime targets, Elasticsearch endpoint mapping, data/setup ladder, Dev Tools Console fallback, and runtime-environment blocker rule.
The companion owns safety boundary, screenshot handoff, live feedback overlay, and controller validation.
Generic `/k-deep-review` runtime contracts should select and pass that overlay, not inline Kibana targets themselves.

## Output

Return only domain additions needed by the primary skill:

- detected domain and evidence
- selected overlay sections
- proposed labels/ownership/footer/release-note/environment additions when relevant
- live UI target packet when relevant
- side-effect gates blocked on approval
