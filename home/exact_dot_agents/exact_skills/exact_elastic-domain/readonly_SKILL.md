---
name: elastic-domain
description: Elastic/Kibana domain overlay for otherwise generic skills and agents. Use when the repo belongs to the elastic GitHub org, when `elastic/kibana` PR/issue/review/live-UI behavior is in scope, or when another skill says to load the Elastic domain overlay. Propose-only unless the active primary skill explicitly permits a side effect.
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
- gather only verified evidence for release-note intent
- include `## Release Note` only when the proposed label is `release_note:fix` or `release_note:feature`
- omit `## Release Note` for `release_note:enhancement`, `release_note:skip`, or any unverified release-note state
- do not skip or defer the label proposal step; the PR body cannot be finalized without it
- if reviewer/ownership guidance is requested, load `kibana-management-ownership`
- never invent issue numbers; use `Closes #X` vs `Addresses #X` intentionally

Elastic PR template variants:

Default template (copy then delete unused sections):

```markdown
Closes #X | Addresses #X

## Summary

-

## Test Plan

Assisted with <Tool> using <Model>
```

Bugfix:

```markdown
Closes #X | Addresses #X

## Summary

-

## Root Cause

-

## Fix

-

## Before/After Screenshots (or Video)

### Before

### After

## Test Plan

-

## Release Note

- Single sentence describing the user-facing behavior change.

Assisted with <Tool> using <Model>
```

Chore/Migration:

```markdown
Closes #X | Addresses #X

## Summary

-

## Rationale

-

## Test Plan

Assisted with <Tool> using <Model>
```

Feature:

```markdown
Closes #X | Addresses #X

## Summary

-

## User-Facing Behavior

-

## Test Plan

-

## Release Note

- Single sentence describing the user-facing behavior change.

Assisted with <Tool> using <Model>
```

`elastic/kibana` issue bodies:

- include environment details when UI or deployment matters
- leave unknown stack/deployment/browser fields blank or marked for follow-up; do not invent them

Kibana issue template:

Copy this template and delete unused sections:

```markdown
## Problem

## Expected

## Actual

## Reproduction

## Environment

- Stack version:
- Deployment (cloud/on-prem):
- Browser/OS (if UI):

## Notes

- Logs / screenshots / sample docs (redact secrets)
- Related issues/PRs
```

## Review and CI additions

- Buildkite URLs for Elastic repos must be handled through the `buildkite` skill and `bk` CLI. Do not fetch `buildkite.com` URLs directly.
- For PR presentations (`present-pr`), fetch only compact Buildkite facts needed for the story: build number, state, commit, and whether failures are current or historical. Do not dump full build metadata unless CI is itself the presentation thesis.
- Kibana labels/backports/version targeting are propose-only through `kibana-labels-propose` unless the user explicitly approves a GitHub mutation.
- Kibana ownership/reviewer targeting is propose-only through `kibana-management-ownership`; side effects go through the `github` skill after approval.
- Known Elastic bot logins for bot-thread classification: `elasticmachine`, `kibanamachine`, `github-actions[bot]`.

## Git commit attribution

When the repo belongs to the `elastic` GitHub org, every commit must include a `Co-authored-by` trailer identifying the AI tool that authored the change. Every commit must include a `Co-authored-by` trailer for the active AI tool.

Known trailer values:

| Tool            | Trailer                                           |
| --------------- | ------------------------------------------------- |
| Cursor          | `Co-authored-by: Cursor <cursoragent@cursor.com>` |
| Claude Code     | `Co-authored-by: Claude <noreply@anthropic.com>`  |
| Copilot         | `Co-authored-by: Copilot <noreply@github.com>`    |
| OpenCode        | `Co-authored-by: opencode <noreply@opencode.ai>`  |
| pi-coding-agent | `Co-authored-by: pi <noreply@anthropic.com>`      |

- Use the identity row matching the tool you are running inside.
- pi-coding-agent normally overrides `GIT_AUTHOR_NAME/EMAIL` directly. If pi handles attribution on its own, skip the trailer to avoid duplication; otherwise use the table row above, replacing the email with the active provider's email if known.
- If the current tool is not in the table, ask for the correct name/email before committing.
- Append the trailer with `git commit --trailer=...`.
- Example: `git commit -m "fix: ..." --trailer="Co-authored-by: Cursor <cursoragent@cursor.com>"`

## Live UI overlay

For `elastic/kibana` live UI verification, load:

```text
~/.agents/skills/elastic-domain/references/kibana-live-ui.md
```

That reference owns the Kibana runtime targets, Elasticsearch endpoint mapping, data/setup ladder, Dev Tools Console fallback, runtime-environment blocker rule, and screenshot handoff details. Generic `/agent-review` runtime contracts should select and pass that overlay, not inline Kibana targets themselves.

## Output

Return only the domain-specific additions needed by the primary skill:

- detected domain and evidence
- selected overlay sections
- proposed labels/ownership/footer/release-note/environment additions when relevant
- live UI target packet when relevant
- side-effect gates that remain blocked on approval
