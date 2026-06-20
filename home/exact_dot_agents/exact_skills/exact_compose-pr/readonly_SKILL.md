---
name: compose-pr
description: Draft a PR title and body as text. Use before creating or editing a PR to compose the description. Text only — no gh side effects.
---

# Compose PR Body

Use when:

- the user wants a PR body draft only (no `gh` side effects)
- `~/.agents/skills/github/SKILL.md` needs a draft body before creating/editing a PR

Scope:

- produces a PR body draft only
- do not change PR metadata; use `~/.agents/skills/github/SKILL.md` for side effects
- read-only `gh`/GitHub API use is allowed only to resolve and fully read PR/issue/comment/media references needed for the draft

Do not use:

- user wants to create/edit PR in GitHub: `~/.agents/skills/github/SKILL.md`
- user is asking for PR review feedback: `~/.agents/skills/review/SKILL.md`

Repo/org-specific overlays:

- A domain overlay is a repo/org-specific skill selected from the verified target repo/org, not guessed from wording. It layers repo-specific PR body policy onto this generic composer.
- Current concrete overlay: for the `elastic` org / `elastic/kibana`, load `~/.agents/skills/elastic-domain/SKILL.md`.
- The overlay decides footer, release-note, label, ownership, and environment additions. This skill stays the generic PR body composer.

First actions:

1. Inspect the current diff/branch context and the user-supplied issue/PR refs.
2. For any PR, issue, comment, thread, asset, URL, or media reference the draft depends on, run the GitHub Context Intake + Reference Resolution gate in `~/.agents/skills/review/references/pr_common.md`.
3. If the PR body needs contested, historical, product, or team-precedent context not settled by direct references, run Ambient Topic Exploration in `~/.agents/skills/review/references/pr_common.md`.
4. Extract only evidence you can verify (summary, test plan, migration notes).
5. If issue linkage or test evidence is missing after intake, keep placeholders instead of inventing details.
6. If the repo belongs to the `elastic` org, load `~/.agents/skills/elastic-domain/SKILL.md` and apply its GitHub/PR composition section.

Rules:

- keep it short and reviewable
- prefer bullets over prose
- test plan must be evidence: commands run + observed result
- when the change removes/replaces long-lived or "legacy"/"obsolete" infrastructure, `## Root Cause` must carry the historical reason it existed and why it no longer applies (see the review skill's Historical-Rationale Gate); do not assert "this was always wrong" without the origin evidence
- for behavior/UI bugs, include portable local reproduction steps that another reviewer can run from a normal checkout; do not replace the repro with only session-specific validation notes
- sanitize public PR text before returning it:
  - do not include machine-specific hosts, ports, paths, temp files, workspace names, browser-session URLs, or local usernames from the author's environment
  - examples to avoid: private hostnames, non-standard local domains, `/tmp/...`, absolute `$HOME` paths, Playwriter/session IDs, one-off account names that are not part of the repro setup
  - use portable wording instead, such as `local app`, `http://localhost:<port>`, `a user with only <privilege>`, or explicit setup steps to create the role/user
- link issues explicitly:
  - `Closes #X` only when merging should close the issue
  - `Addresses #X` when it should not auto-close
  - never invent issue numbers

Output:

- Return only the PR body draft, ready to paste or hand to `~/.agents/skills/github/SKILL.md`.
- If important inputs are missing, say exactly which placeholders still need confirmation.

## General template

```markdown
Closes #X | Addresses #X

## Summary

-

## Test Plan

-
```
