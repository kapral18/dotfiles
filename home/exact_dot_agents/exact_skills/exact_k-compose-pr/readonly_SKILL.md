---
name: k-compose-pr
description: "Use when drafting a PR title/body or PR publication packet before creating or editing a PR; includes template/screenshots/test-plan/metadata handoff, no gh side effects."
---

# Compose PR Body

Use when:

- the user wants a PR title/body draft or PR publication packet only (no `gh` side effects)
- `~/.agents/skills/k-github/SKILL.md` needs a draft body before creating/editing a PR

Scope:

- produces a PR title/body draft and PR publication packet only
- do not change PR metadata; use `~/.agents/skills/k-github/SKILL.md` for side effects
- read-only `gh`/GitHub API use is allowed only to resolve and fully read PR/issue/comment/media references needed for the draft

Do not use:

- user wants to create/edit PR in GitHub: `~/.agents/skills/k-github/SKILL.md`
- user is asking for PR review feedback: `~/.agents/skills/k-review/SKILL.md`

Repo/org-specific overlays:

- A domain overlay is a repo/org-specific skill selected from the verified target repo/org, not guessed from wording.
  It layers repo-specific PR body policy onto this generic composer.
- Current concrete overlay: for the `elastic` org / `elastic/kibana`, load `~/.agents/skills/k-elastic-domain/SKILL.md`.
- The overlay decides footer, release-note, label, ownership, and environment additions. This skill stays the generic PR body composer.

First actions:

1. Inspect the current diff/branch context and the user-supplied issue/PR refs.
2. For any PR, issue, comment, thread, asset, URL, or media reference the draft depends on, run the GitHub Context Intake + Reference Resolution gate.
   The gate lives in `~/.agents/skills/k-review/references/pr_common.md`.
   The gate is not complete from previews or sliced fields; read full raw bodies/comments first, then summarize.
3. If the PR body needs contested, historical, product, or team-precedent context not settled by direct references, run Ambient Topic Exploration.
   That workflow lives in `~/.agents/skills/k-review/references/pr_common.md`.
4. Extract only evidence you can verify (summary, test plan, migration notes).
5. If issue linkage or test evidence is missing after intake, keep placeholders instead of inventing details.
6. If the repo belongs to the `elastic` org, load `~/.agents/skills/k-elastic-domain/SKILL.md` and apply its GitHub/PR composition section.
7. Build the PR publication packet.
   This is the single handoff gate to `k-github`; do not hand off while any required field is missing or `blocked`. Required fields:
   - `template`: selected template, selection reason, required-section checklist, and `status: satisfied | blocked`.
     If the repo/domain overlay provides templates, load the referenced template file before drafting and draft against one selected template, not a freeform section list.
   - `screenshots`: `captured | not_applicable | blocked | explicitly_skipped`.
     Screenshot proof is required when the diff touches UI/runtime behavior, linked context includes screenshots/media, or the Test Plan includes manual UI steps.
     Required proof means reuse a `/build` `k-ui-proof` manifest, or load `~/.agents/skills/k-ui-proof/SKILL.md` and run it head-only.
     For UI behavior bugs whose key assertion is non-visual (clipboard, keyboard, focus, network), still capture human-visible trigger/result states and record the non-visual assertion in the Test Plan.
     Captured proof includes folder/filename mapping and folder-open/provided status; explicit skips include user approval evidence.
   - `test_plan`: issue reproduction/expected/actual coverage, commands run, and observed results.
     When the effort carries a `,proof` ledger, check `,proof list`, run `,proof --topic <topic> report` for the matching topic, and fold the receipt into the evidence/Test Plan section.
     Quote criteria, evidence IDs, and verdicts instead of pasting raw logs; never include artifacts that could carry secrets.
   - `metadata`: proposed labels/assignees/milestone/projects, source skill/rationale, and `status: none | not_applicable | approved_to_apply | applied | deferred | pending_approval`.
     If metadata is proposed but not approved for application, the packet status is `pending_approval` unless the user explicitly defers it.
     Completion criterion: the packet is complete, or the composition is blocked with exact missing fields.
8. Keep the packet with the draft for any handoff to `k-github`: title source, body source, linked issue intake, template, screenshots, Test Plan, metadata, and unresolved placeholders.

Rules:

- keep it short and reviewable
- prefer bullets over prose
- test plan must be evidence: commands run + observed result
- template compliance:
  - do not collapse required template sections into `## Summary`
  - required explanatory sections such as `## Root Cause`, `## Fix`, `## Rationale`, or `## User-Facing Behavior` must appear as their own headings when the selected template includes them
  - before handoff, compare the final draft headings against the selected template's required-section checklist
- PR Test Plan completeness gate:
  - if any linked/closing issue has `## Reproduction`, `Expected`, or `Actual`, adapt the observable steps into `## Test Plan`
  - include the expected observable result after the fix
  - include commands run + observed results separately from manual/observable verification steps
  - if manual repro was not run, say so and keep the portable steps as reviewer-run verification
- when the change removes/replaces long-lived or "legacy"/"obsolete" infrastructure, `## Root Cause` must carry the historical reason it existed and why it no longer applies (see the review skill's Historical-Rationale Gate); do not assert "this was always wrong" without the origin evidence
- for behavior/UI bugs, include portable local reproduction steps that another reviewer can run from a normal checkout;
  do not replace the repro with only session-specific validation notes
- sanitize public PR text before returning it:
  - do not include machine-specific hosts, ports, paths, temp files, workspace names, browser-session URLs, or local usernames from the author's environment
  - examples to avoid: private hostnames, non-standard local domains, `/tmp/...`, absolute `$HOME` paths, Playwriter/session IDs, one-off account names that are not part of the repro setup
  - use portable wording instead, such as `local app`, `http://localhost:<port>`, `a user with only <privilege>`, or explicit setup steps to create the role/user
- screenshots (UI-facing changes only):
  - when screenshot proof is captured, add a `## Screenshots` section listing each shot as a caption plus an `attach: <filename>` placeholder the user drags into the GitHub PR
  - never put the local `/tmp/<folder-name>/` path in the PR body (the sanitize rule above);
    keep the folder + filename→path mapping in the PR publication packet so the user knows which file to attach
  - the agent does not upload images; GitHub image embedding is a manual drag-drop the user performs, so leave the attach placeholder rather than a fabricated image URL
  - before any PR create/edit handoff, open the screenshot folder or otherwise give the user the folder path plus filename mapping so the files can be dragged into GitHub
  - omit the section only for `not_applicable` or `explicitly_skipped`; do not omit it for `required` or `blocked`
- decision log: when the change embodies a decision with observable consequences for someone else —
  a different API shape, privilege model, error response, storage format, or default —
  add a `## Decisions` section with one bullet per decision: `**<decision>** — risk: <what goes wrong if this was the wrong call>`.
  Internal implementation choices do not qualify; omit the section when no qualifying decision exists.
- link issues explicitly:
  - `Closes #X` only when merging should close the issue
  - `Addresses #X` when it should not auto-close
  - never invent issue numbers

Output:

- Return the PR title/body draft and PR publication packet, ready to hand to `~/.agents/skills/k-github/SKILL.md`.
- If important inputs are missing, say exactly which placeholders still need confirmation.
- Always include the PR publication packet. A packet with a `blocked` required field cannot be handed to `k-github` for publication.
  Include template status: selected template, why it applies, required sections present, sections omitted with template-allowed reasons, and blockers.
  Include screenshot status.
  When screenshots were captured, include the `## Screenshots` section in the body with attach placeholders, list each proof set's `/tmp/<folder-name>/` + filename→path mapping outside the body, and open/provide the folder so the user can attach the files to the PR.
  When screenshots were not captured, the ledger must say `not_applicable`, `blocked`, or `explicitly_skipped` with evidence;
  `blocked` cannot be handed to `k-github` for publication.
  Include metadata status: proposed metadata, source skill/rationale, and whether it is approved to apply, applied, deferred, or still pending approval.
- When handing the draft to `k-github` for PR creation/editing, include the packet outside the PR body so the GitHub skill can build its publication preflight.

## General template

```markdown
Closes #X | Addresses #X

## Summary

-

## Test Plan

-

## Screenshots

<!-- UI-facing changes only; omit otherwise. One bullet per captured shot; attach the file from its /tmp/<folder-name>/ folder (see the PR publication packet). -->

- <caption — what this proves> — attach: `<filename>.png`
```
