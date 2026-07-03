---
name: elastic-domain
description: "Use when the target is Elastic org, elastic/kibana, or Elastic/Kibana Buildkite, SCSI, labels, ownership, live UI, or domain policy."
---

# Elastic Domain Overlay

This skill is a domain overlay. It adds Elastic/Kibana-specific policy to a primary generic skill; it does not replace that skill.

Use when:

- the current repo or target object belongs to the `elastic` GitHub org
- the current repo is `elastic/kibana`
- another skill says to load the Elastic domain overlay
- handling Elastic Buildkite, SCSI, Kibana labels, Kibana ownership, Kibana live UI, or Kibana Dev Tools Console behavior

Do not use:

- as a standalone review, GitHub, git, or compose workflow
- outside Elastic/Kibana contexts unless a user explicitly asks for these domain rules
- to post, label, resolve, commit, push, or mutate anything by itself

## Detection

Verify the domain from evidence before applying these rules.

- GitHub target: `gh repo view --json nameWithOwner --jq .nameWithOwner`
- local repo fallback: `git remote -v`, matching an `elastic/<repo>` remote
- Kibana-specific behavior applies only when the repo is exactly `elastic/kibana`

If detection is unavailable, keep the primary generic skill behavior and state that Elastic-specific rules could not be verified.

## Layering contract

1. Run the primary skill's generic workflow first.
2. Load this overlay only for the domain-specific additions below.
3. Do not duplicate generic mechanics here: routing, PR intake, pending-review reconciliation, publication gates, and review judging remain owned by their primary skills.
4. If this overlay conflicts with the primary skill, the safer/gated behavior wins.

## GitHub and PR composition

Apply when the primary skill is `compose-pr`, `compose-issue`, `github`, or a review flow preparing GitHub-visible text.

Precedence for `elastic/kibana` PR composition:

- this overlay specializes the generic `github`, `kbn-github`, and `compose-pr` title/body guidance for Kibana
- this overlay owns Kibana-specific title style, PR body sections, release-note inclusion, and assistance footer policy
- `kibana-labels-propose` owns Kibana label/backport/version classification; invoke it and use its output instead of duplicating label inference here
- the `github` / `kbn-github` skills own GitHub mechanics and approval gates for applying metadata
- once this overlay applies, generic skills must not invent fallback Kibana title style, labels, release-note state, or footer policy.
  If this overlay or `kibana-labels-propose` has not produced the needed domain packet, stop and obtain that packet instead of guessing.

Elastic/Kibana public text sanitization:

- for behavior/UI bugs, use portable local reproduction wording such as `local Kibana`, `http://localhost:5601`, `a user with only <privilege>`, or explicit setup steps to create the role/user
- do not publish private hostnames, non-standard local domains, `/tmp/...`, absolute workspace paths, browser automation session names, or one-off local account names unless the public text explicitly tells the reader how to create them

Elastic org PR bodies:

- append an `Assisted with <Tool> using <Model>` footer at the very end
- use the actual tool/model when known
- replace `<model>` with the actual model name you are running as (e.g. `Claude 4.6 Opus`, `GPT-5.4`, `Gemini 2.5 Pro`)
- if the current tool is unknown, use a reasonable label and ask the user to confirm
- put the footer after all other sections, separated by a blank line
- gather only verified evidence for summary, root cause/fix, and test plan

Known tool labels:

| Tool            | Footer label                                  |
| --------------- | --------------------------------------------- |
| Cursor          | `Assisted with Cursor using <model>`          |
| Claude Code     | `Assisted with Claude Code using <model>`     |
| Copilot         | `Assisted with Copilot using <model>`         |
| OpenCode        | `Assisted with OpenCode using <model>`        |
| pi-coding-agent | `Assisted with pi-coding-agent using <model>` |

`elastic/kibana` PR bodies:

- before drafting the PR body, invoke `kibana-labels-propose` via the Skill tool to propose labels/backports/version targeting
- PR titles should use Kibana's bracketed area style when there is a clear owning area, e.g. `[Console] Fix ...`.
  Derive the bracket from the linked issue title, owning changed paths, or recent same-area PR precedent.
  Do not use a Conventional Commit header as the PR title unless local Kibana precedent for that exact area uses it.
  If multiple bracket prefixes are plausible and evidence does not choose one, ask before creating or editing the PR.
- gather only verified evidence for release-note intent
- include `## Release Note` only when the proposed label is `release_note:fix` or `release_note:feature`
- omit `## Release Note` for `release_note:enhancement`, `release_note:skip`, or any unverified release-note state
- do not skip or defer the label proposal step; the PR body cannot be finalized without it
- if reviewer/ownership guidance is requested, load `kibana-management-ownership`
- never invent issue numbers; use `Closes #X` vs `Addresses #X` intentionally

`elastic/kibana` issue bodies:

- include environment details when UI or deployment matters
- leave unknown stack/deployment/browser fields blank or marked for follow-up; do not invent them

Copy-paste PR body templates (Default/Bugfix/Chore/Feature) and the Kibana issue template live in `~/.agents/skills/elastic-domain/references/pr-issue-templates.md`.

## Kibana planning fork checklist

Apply when the primary skill is `spec` (or any SOP §3.0 intent loop) and the verified target repo is `elastic/kibana`.

Consult `~/.agents/skills/elastic-domain/references/kibana-planning-forks.md` to seed the fork inventory:
API versioning, Saved Objects/migrations, privileges, dependencies, feature flags, backports, test placement, alerting, and instrumentation.
Evidence-first: answer items from the issue/diff/codebase before asking; only genuine gaps become fork-closing questions.

## Review and CI additions

- Buildkite URLs for Elastic repos must be handled through the `buildkite` skill and `bk` CLI. Do not fetch `buildkite.com` URLs directly.
- For PR presentations (`present-pr`), fetch only compact Buildkite facts needed for the story:
  build number, state, commit, and whether failures are current or historical.
  Do not dump full build metadata unless CI is itself the presentation thesis.
- Kibana labels/backports/version targeting are propose-only through `kibana-labels-propose` unless the user explicitly approves a GitHub mutation.
- Kibana ownership/reviewer targeting is propose-only through `kibana-management-ownership`;
  side effects go through the `github` skill after approval.
- When the review Signal-Quality Gate (`~/.agents/skills/review/references/judging_core.md`) triggers on Elastic observability surfaces, this overlay owns the query/product specifics:
  - ES|QL / Query DSL queries must be syntactically and semantically valid for the target stack version
  - field references must match the expected mapping types
  - aggregation bucket sizes must fit the expected data volume
  - flag queries that can time out or OOM on large datasets
- Known Elastic bot logins for bot-thread classification: `elasticmachine`, `kibanamachine`, `github-actions[bot]`.

## Git commit attribution

When the repo belongs to the `elastic` GitHub org, every commit must include a `Co-authored-by` trailer identifying the AI tool that authored the change.

Known trailer values:

| Tool            | Trailer                                           |
| --------------- | ------------------------------------------------- |
| Cursor          | `Co-authored-by: Cursor <cursoragent@cursor.com>` |
| Claude Code     | `Co-authored-by: Claude <noreply@anthropic.com>`  |
| Copilot         | `Co-authored-by: Copilot <noreply@github.com>`    |
| OpenCode        | `Co-authored-by: opencode <noreply@opencode.ai>`  |
| pi-coding-agent | `Co-authored-by: pi <noreply@anthropic.com>`      |

- Use the identity row matching the tool you are running inside.
- pi-coding-agent normally overrides `GIT_AUTHOR_NAME/EMAIL` directly.
  If pi handles attribution on its own, skip the trailer to avoid duplication;
  otherwise use the table row above, replacing the email with the active provider's email if known.
- If the current tool is not in the table, ask for the correct name/email before committing.
- Append the trailer with `git commit --trailer=...`.
- Example: `git commit -m "fix: ..." --trailer="Co-authored-by: Cursor <cursoragent@cursor.com>"`

## Live UI overlay

For `elastic/kibana` live UI verification, load:

```text
~/.agents/skills/elastic-domain/references/kibana-live-ui.md
```

That reference owns the Kibana runtime targets, Elasticsearch endpoint mapping, data/setup ladder, Dev Tools Console fallback, runtime-environment blocker rule, and screenshot handoff details.
Generic `/agent-review` runtime contracts should select and pass that overlay, not inline Kibana targets themselves.

## Output

Return only the domain-specific additions needed by the primary skill:

- detected domain and evidence
- selected overlay sections
- proposed labels/ownership/footer/release-note/environment additions when relevant
- live UI target packet when relevant
- side-effect gates that remain blocked on approval
