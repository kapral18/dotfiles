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

Repo/org-specific overlays:

- A domain overlay is a repo/org-specific skill selected from the verified target repo/org, not guessed from wording. It layers repo-specific issue body policy onto this generic composer.
- Current concrete overlay: for the `elastic` org / `elastic/kibana`, load `~/.agents/skills/elastic-domain/SKILL.md`.
- The overlay decides environment fields and repo-specific issue details. This skill stays the generic issue body composer.

First actions:

1. If the problem statement, repro, logs, screenshots, or notes reference any PR, issue, comment, thread, asset, URL, or media, run the GitHub Context Intake + Reference Resolution gate in `~/.agents/skills/review/references/pr_common.md`.
2. If the issue body needs contested, historical, product, or team-precedent context not settled by direct references, run Ambient Topic Exploration in `~/.agents/skills/review/references/pr_common.md`.
3. Identify the problem statement, expected behavior, actual behavior, and reproduction from verified evidence.
4. Keep repro steps concrete and ordered.
5. Convert local-only observations into portable repro steps; do not paste session-specific URLs, machine hostnames, temp paths, workspace paths, browser automation session names, or local usernames into public issue text.
6. If logs/screenshots are referenced, include only what materially helps and redact secrets.
7. If the repo belongs to the `elastic` org or is `elastic/kibana`, load `~/.agents/skills/elastic-domain/SKILL.md` and apply its issue composition section.

Rules:

- be concrete and reproducible
- prefer numbered repro steps
- include logs/screenshots only if they add diagnostic value; redact secrets
- public issue text must be portable for other maintainers:
  - avoid private hostnames, non-standard local domains, `/tmp/...`, absolute `$HOME` paths, Playwriter/session IDs, and one-off local account names unless the issue explicitly instructs how to create them
  - use generic terms like `local app`, `http://localhost:<port>`, `a user with only <privilege>`, or explicit setup steps

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
