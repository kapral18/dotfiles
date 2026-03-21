---
name: compose-pr
description: |-
  Draft a PR title and body as text. Use before creating or editing a PR
  to compose the description. Text only — no gh side effects.
---

# Compose PR Body

Use when:

- the user wants a PR body draft only (no `gh` side effects)
- `~/.agents/skills/github/SKILL.md` needs a draft body before creating/editing
  a PR

Scope:

- produces a PR body draft only
- do not run `gh` or change PR metadata; use `~/.agents/skills/github/SKILL.md`
  for side effects

Do not use:

- user wants to create/edit PR in GitHub: `~/.agents/skills/github/SKILL.md`
- user is asking for PR review feedback: `~/.agents/skills/review/SKILL.md`

First actions:

1. Inspect the current diff/branch context and the user-supplied issue refs.
2. Extract only evidence you can verify (summary, test plan, migration notes).
3. If issue linkage or test evidence is missing, keep placeholders instead of
   inventing details.
4. If the repo belongs to the `elastic` org, use the Elastic org variant section
   below.

Rules:

- keep it short and reviewable
- prefer bullets over prose
- test plan must be evidence: commands run + observed result
- link issues explicitly:
  - `Closes #X` only when merging should close the issue
  - `Addresses #X` when it should not auto-close
  - never invent issue numbers

Output:

- Return only the PR body draft, ready to paste or hand to
  `~/.agents/skills/github/SKILL.md`.
- If important inputs are missing, say exactly which placeholders still need
  confirmation.

## General template

```markdown
Closes #X | Addresses #X

## Summary

-

## Test Plan

-
```

## Elastic org variant

Use when the repo belongs to the `elastic` GitHub org.

Additional first actions:

1. Verify the repo belongs to the `elastic` org.
2. Gather only verified evidence for summary, root cause/fix, test plan, and
   (for Kibana) release-note intent.

Additional rules:

- never invent issue numbers; use `Closes #X` vs `Addresses #X` intentionally
- append an "Assisted with" footer at the very end of every PR body (see footer
  table below)

Assisted-with footer (elastic org repos only):

Every PR body must end with a one-line attribution identifying the AI tool and
model used. Format: `Assisted with <Tool> using <Model>`.

Known tool labels:

| Tool            | Label example                                 |
| --------------- | --------------------------------------------- |
| Cursor          | `Assisted with Cursor using <model>`          |
| Claude Code     | `Assisted with Claude Code using <model>`     |
| Copilot         | `Assisted with Copilot using <model>`         |
| OpenCode        | `Assisted with OpenCode using <model>`        |
| pi-coding-agent | `Assisted with pi-coding-agent using <model>` |

- Replace `<model>` with the actual model name you are running as (e.g.
  `Claude 4.6 Opus`, `GPT-5.4`, `Gemini 2.5 Pro`).
- If the current tool is not in the table, use a reasonable label and ask the
  user to confirm.
- The footer goes after all other sections, separated by a blank line.

### Kibana-specific rules

Additional rules when the repo is `elastic/kibana`:

- Always load `~/.agents/skills/kibana-labels-propose/SKILL.md` to determine the
  correct release note label — the `## Release Note` section inclusion depends
  on it.
- Include a `## Release Note` section only when the change warrants
  `release_note:fix` or `release_note:feature`; omit the section entirely for
  all other release note labels (`release_note:enhancement`,
  `release_note:skip`).
- If the user also asks for reviewer/ownership guidance, load the Kibana
  ownership skill before finalizing the draft.

Required guidance:

- label proposals (propose-only):
  `~/.agents/skills/kibana-labels-propose/SKILL.md`

Optional guidance:

- Kibana Management ownership signals:
  `~/.agents/skills/kibana-management-ownership/SKILL.md`

### Templates (Elastic org)

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
