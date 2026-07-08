---
name: compose-issue
description: "Use when drafting an issue title/body or issue publication packet before creating or editing a GitHub issue; includes issue_type/metadata/relationships handoff, no gh side effects."
---

# Compose Issue

Use when:

- the user wants an issue title/body draft or issue publication packet only (no `gh` side effects)
- `~/.agents/skills/github/SKILL.md` needs issue text before creating/editing an issue

Scope:

- produces an issue title/body draft and issue publication packet only
- do not create issues via `gh` here; use `~/.agents/skills/github/SKILL.md` for GitHub side effects
- read-only `gh`/GitHub API use is allowed only to resolve and fully read PR/issue/comment/media references needed for the draft

Do not use:

- user wants to create/edit the issue in GitHub: `~/.agents/skills/github/SKILL.md`

Repo/org-specific overlays:

- A domain overlay is a repo/org-specific skill selected from the verified target repo/org, not guessed from wording.
  It layers repo-specific issue body policy onto this generic composer.
- Current concrete overlay: for the `elastic` org / `elastic/kibana`, load `~/.agents/skills/elastic-domain/SKILL.md`.
- The overlay decides environment fields and repo-specific issue details. This skill stays the generic issue body composer.

First actions:

1. If the problem statement, repro, logs, screenshots, or notes reference any PR, issue, comment, thread, asset, URL, or media, run the GitHub Context Intake + Reference Resolution gate.
   The gate lives in `~/.agents/skills/review/references/pr_common.md`.
   The gate is not complete from previews or sliced fields; read full raw bodies/comments first, then summarize.
2. If the issue body needs contested, historical, product, or team-precedent context not settled by direct references, run Ambient Topic Exploration.
   That workflow lives in `~/.agents/skills/review/references/pr_common.md`.
3. Identify the problem statement, expected behavior, actual behavior, and reproduction from verified evidence.
4. Keep repro steps concrete and ordered.
5. Convert local-only observations into portable repro steps.
   Do not paste session-specific URLs, machine hostnames, temp paths, workspace paths, browser automation session names, or local usernames into public issue text.
6. If logs/screenshots are referenced, include only what materially helps and redact secrets.
7. If issue creation is in scope, verify `gh issue create --help` support for `--type name`.
   If the target repo exposes GitHub issue types, read the actual type names before choosing one.
8. If the repo belongs to the `elastic` org or is `elastic/kibana`, load `~/.agents/skills/elastic-domain/SKILL.md`.
   Apply its issue composition section.
9. Build the issue publication packet.
   This is the single handoff gate to `github`; do not hand off while any required field is missing or `blocked`. Required fields:
   - `issue_type`: exact GitHub issue type, source evidence, and `status: approved_to_apply | pending_approval | not_applicable | blocked`.
     When the target repo supports GitHub issue types, this field is required; labels do not satisfy it.
   - `metadata`: labels, assignees, milestone, projects, source evidence, and `status: none | not_applicable | approved_to_apply | applied | deferred | pending_approval`.
   - `relationships`: parent issue/sub-issue links, linked issues/PRs, and status.
   - `duplicate_check`: queries run, hits read, and duplicate verdict.
   - `intake`: full references read, skipped references with reasons, and what each contributed.
     Completion criterion: the packet is complete, or the composition is blocked with exact missing fields.

Rules:

- be concrete and reproducible
- prefer numbered repro steps
- include logs/screenshots only if they add diagnostic value; redact secrets
- public issue text must be portable for other maintainers:
  - avoid private hostnames, non-standard local domains, `/tmp/...`, absolute `$HOME` paths, Playwriter/session IDs, and one-off local account names unless the issue explicitly instructs how to create them
  - use generic terms like `local app`, `http://localhost:<port>`, `a user with only <privilege>`, or explicit setup steps
- GitHub issue type:
  - pick from the repo's actual issue types, not labels or memory
  - `Bug` is appropriate for verified unexpected behavior, regressions, crashes, broken UI, incorrect output, or failing existing workflows
  - `Enhancement` is appropriate for feature requests, improvements, and new functionality
  - `Task`, `Meta`, `Epic`, and other planning types require explicit user/domain evidence
  - keep the old `bug` label only when the repo still uses it for triage; it does not satisfy the GitHub issue type gate

Output:

- Return the issue title/body draft and the issue publication packet.
- If crucial repro or environment detail is missing, call it out explicitly rather than guessing.
- When handing the draft to `github` for issue creation/editing, include the packet outside the issue body so the GitHub skill can build its publication preflight.

## General template

```markdown
## Problem

## Expected

## Actual

## Reproduction

## Notes
```
