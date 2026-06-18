---
name: compose-issue
description: Draft an issue title and body as text. Use before creating or editing an issue to compose the description. Text only — no gh side effects.
---

# Compose Issue Body

Use when:

- the user wants an issue body draft only (no `gh` side effects)
- `~/.agents/skills/github/SKILL.md` needs issue text before creating/editing an issue

Scope:

- produces an issue body draft only
- do not create issues via `gh` here; use `~/.agents/skills/github/SKILL.md` for GitHub side effects
- read-only `gh`/GitHub API use is allowed only to resolve and fully read PR/issue/comment/media references needed for the draft

Do not use:

- user wants to create/edit the issue in GitHub: `~/.agents/skills/github/SKILL.md`

First actions:

1. If the problem statement, repro, logs, screenshots, or notes reference any PR, issue, comment, thread, asset, URL, or media, run the GitHub Context Intake + Reference Resolution gate in `~/.agents/skills/review/references/pr_common.md`.
2. If the issue body needs contested, historical, product, or team-precedent context not settled by direct references, run Ambient Topic Exploration in `~/.agents/skills/review/references/pr_common.md`.
3. Identify the problem statement, expected behavior, actual behavior, and reproduction from verified evidence.
4. Keep repro steps concrete and ordered.
5. Convert local-only observations into portable repro steps; do not paste session-specific URLs, machine hostnames, temp paths, workspace paths, browser automation session names, or local usernames into public issue text.
6. If logs/screenshots are referenced, include only what materially helps and redact secrets.
7. If the repo is Elastic/Kibana, use the Elastic variant section below.

Rules:

- be concrete and reproducible
- prefer numbered repro steps
- include logs/screenshots only if they add diagnostic value; redact secrets
- public issue text must be portable for other maintainers:
  - avoid private hostnames, non-standard local domains, `/tmp/...`, absolute `$HOME` paths, Playwriter/session IDs, and one-off local account names unless the issue explicitly instructs how to create them
  - use generic terms like `local Kibana`, `http://localhost:5601`, `a user with only <privilege>`, or explicit setup steps

Output:

- Return only the issue body draft.
- If crucial repro or environment detail is missing, call it out explicitly rather than guessing.

## General template

```markdown
## Problem

## Expected

## Actual

## Reproduction

## Notes
```

## Elastic / Kibana variant

Use when the repo is Elastic/Kibana.

Additional first actions:

1. Verify the repo/context is Elastic/Kibana.
2. Gather reproducible problem, expected behavior, actual behavior, and environment details from evidence.
3. Leave unknown stack/deployment/browser fields blank or marked for follow-up; do not invent them.

Additional rules:

- include environment details when UI or deployment matters

Template (copy then delete unused sections):

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
