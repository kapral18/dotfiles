---
name: k-elastic-domain
description: "Use when target is Elastic org, elastic/kibana, Buildkite, SCSI, labels, ownership, live UI, or domain policy."
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

1. Run the primary skill's generic workflow first.
2. Load this overlay only for domain additions below.
3. Do not duplicate generic mechanics: routing, PR intake, pending-review reconciliation, publication gates, and review judging stay with primary skills.
4. If this overlay conflicts with the primary skill, safer/gated behavior wins.

## GitHub and PR composition

Apply with `k-compose-pr`, `k-compose-issue`, `k-github`, or review flows preparing GitHub-visible text.

Precedence for `elastic/kibana` PR composition:

- this overlay owns Kibana-specific title style, PR body sections, release-note inclusion, and assistance footer policy
- `k-kibana-labels-propose` owns Kibana label/backport/version classification; invoke it and use its packet
- `k-github` owns GitHub mechanics and approval gates for applying metadata
- once this overlay applies, generic skills must not invent fallback Kibana title style, labels, release-note state, or footer policy;
  stop and obtain the domain packet instead of guessing

Public text sanitization:

- For behavior/UI bugs, use portable local repro wording: `local Kibana`, `http://localhost:5601`, `a user with only <privilege>`, or explicit role/user setup.
- Do not publish private hostnames, non-standard local domains, `/tmp/...`, absolute workspace paths, browser session names, or one-off local accounts unless the text tells readers how to create them.

Elastic org PR bodies:

- Append `Assisted with <Tool> using <Model>` at the very end, after all other sections and a blank line.
- Use the actual tool/model when known; if unknown, use a reasonable label and ask the user to confirm.
- Known labels: Cursor, Claude Code, Copilot, OpenCode, pi-coding-agent.
- Gather only verified evidence for summary, root cause/fix, and test plan.

`elastic/kibana` PR bodies:

- Before drafting, invoke `k-kibana-labels-propose` for labels/backports/version targeting.
- Before drafting, read `~/.agents/skills/k-elastic-domain/references/pr-issue-templates.md` and select exactly one Kibana PR template:
  - `Bugfix`: linked issue/proposed labels indicate `bug`, `regression`, or `release_note:fix`
  - `Feature`: proposed label is `release_note:feature`
  - `Chore/Migration`: chores, migrations, refactors, or test-only maintenance
  - `Default`: only when the others do not fit
- Fill the PR publication packet `template` field: selected template, evidence, required headings present, omitted sections with template-allowed reasons.
  For `Bugfix`, `## Root Cause` and `## Fix` are standalone; screenshots use the packet `screenshots` field and require uploaded embeds or explicit skip approval.
- PR titles should use Kibana's bracketed area style when evidence chooses an area, e.g. `[Console] Fix ...`.
  Derive from linked issue, changed-path ownership, or same-area PR precedent; ask if multiple brackets remain plausible.
  Do not use a Conventional Commit header as the PR title unless that exact area has precedent.
- Include `## Release Note` only for `release_note:fix` or `release_note:feature`; omit for enhancement/skip/unverified states.
- Do not skip/defer label proposal; body finalization requires it.
- If reviewer/ownership guidance is requested, load `k-kibana-management-ownership`.
- Never invent issue numbers; choose `Closes #X` vs `Addresses #X` intentionally.

`elastic/kibana` issue bodies: include environment details when UI or deployment matters;
leave unknown stack/deployment/browser fields blank or marked for follow-up; do not invent them.

Templates live in `~/.agents/skills/k-elastic-domain/references/pr-issue-templates.md`.

## Kibana planning fork checklist

Apply with `k-spec` or any SOP §3.0 intent loop when the verified repo is `elastic/kibana`.
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

When the repo belongs to `elastic`, every commit needs a `Co-authored-by` trailer for the AI tool. Use the active tool identity:

- Cursor: `Co-authored-by: Cursor <cursoragent@cursor.com>`
- Claude Code: `Co-authored-by: Claude <noreply@anthropic.com>`
- Copilot: `Co-authored-by: Copilot <noreply@github.com>`
- OpenCode: `Co-authored-by: opencode <noreply@opencode.ai>`
- pi-coding-agent: `Co-authored-by: pi <noreply@anthropic.com>`

If pi already overrides `GIT_AUTHOR_NAME/EMAIL`, skip the trailer to avoid duplication.
If the current tool is unknown, ask for name/email before committing. Append with `git commit --trailer=...`.

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
