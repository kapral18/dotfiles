# PR Publication Packet Reference

Load when building the required PR publication packet for `k-github`. The gate is not complete from previews or sliced fields.

## Required fields

- `template`: selected template, selection reason, required-section checklist, and `status: satisfied | blocked`.
  If an overlay provides templates, load the actual template file and draft against one selected template.
- `screenshots`: `captured | not_applicable | blocked | explicitly_skipped`.
  Visual proof is required when the diff touches UI/runtime behavior, linked context includes screenshots/media, or the Test Plan includes manual UI steps.
  Load and follow `~/.agents/skills/k-ui-capture/references/proof-mode.md` in full:
  build its Behavior inventory first, apply its coverage plan and comparison frames, run its Existing published proof gate before capturing for an existing PR, and complete its Claim map before embedding.
  Required proof means reuse a `/k-build` live-UI proof manifest, or run that proof-mode contract head-only.
  Body Screenshots/Videos carry `baseline` pairs; mid-change tip↔tip pairs go in a separate comment when requested.
  For non-visual UI behavior bugs (clipboard, keyboard, focus, network), capture human-visible trigger/result states and record the non-visual assertion in the Test Plan.
  Captured proof includes folder/filename mapping; explicit skips include user approval evidence.
- `test_plan`: reviewer-runnable steps, issue reproduction/expected/actual coverage, commands run, and observed results.
  If a matching `,proof` ledger exists, select it with `,proof list --json` and inspect `,proof --topic <topic> status --json`.
  Consume it as completion proof only when `allowed` is true, `finalized_at` is set, and `seal_status` is `ok`.
  Run `,proof --topic <topic> report` and quote criteria, evidence IDs, and verdicts instead of raw logs.
  If the ledger is failing, unfinalized, or has a broken seal, report that state;
  presenting it as proof or finishing it retroactively during PR composition is off limits.
- `metadata`: proposed labels/assignees/milestone/projects, source skill/rationale, and `status: none | not_applicable | approved_to_apply | applied | deferred | pending_approval`.
  Proposed-but-unapproved metadata is `pending_approval` unless the user explicitly defers it.
- Keep PR reviewer fields unset; GitHub handles reviewer assignment automatically.

Completion criterion: the packet is complete, or composition is blocked with exact missing fields.

## Body rules

- Keep it short and reviewable; prefer bullets over prose.
- Test Plan must be evidence: runnable command or manual step, expected result, and observed result.
- Before proposing a Test Plan command or manual step, verify it from local source, CLI help, linked issue steps, or a safe probe.
  If it is not verified, keep it as a composer-only placeholder outside the PR body; do not present it as runnable Test Plan evidence.
- Test Plan MUST NOT mirror or enumerate changed test paths, spec filenames, fixtures, snapshots, or diff file lists as the plan.
  Mention a path only when it is part of a command or concrete repro step a reviewer can run from a normal checkout.
- Manual Test Plan steps must be reader-executable: each step has one action or one expected observation, using literal UI labels, commands, field values, keystrokes, and API names.
  Do not combine setup, choice, and verification in one sentence.
- Before simplifying a behavioral Test Plan, run the false-positive check: would the plan still pass without the fix?
  Preserve required setup state, such as warming a cache before testing cache invalidation, when that state makes the old bug observable.
- If the requested `## Test Plan` must be manual-only, keep executed commands and observed local validation in the publication packet or a separate non-Test-Plan section instead of mixing them into the manual steps.
- Do not collapse required template sections into `## Summary`.
  Required explanatory sections such as `## Root Cause`, `## Fix`, `## Rationale`, or `## User-Facing Behavior` must appear as their own headings when selected by the template.
  Before handoff, compare final headings against the template checklist.
- **PR Test Plan completeness gate**: if any linked/closing issue has `## Reproduction`, `Expected`, or `Actual`, adapt observable steps into `## Test Plan`; include the expected observable result after the fix; include commands run + observed results separately from manual/observable verification steps; if manual repro was not run, say so and keep portable reviewer-run steps.
- For removed/replaced long-lived or “legacy” infrastructure, `## Root Cause` must carry why it existed and why it no longer applies;
  do not say “always wrong” without origin evidence.
- For behavior/UI bugs, include portable local reproduction steps another reviewer can run from a normal checkout;
  do not replace repro with session-only validation notes.
- Sanitize public PR text: no machine-specific hosts, ports, paths, temp files, workspace names, browser-session URLs, or local usernames.
  Prefer portable wording such as `local app`, `http://localhost:<port>`, `a user with only <privilege>`, or setup steps.
- Screenshots: when captured, add `## Screenshots` with bold caption + `user-attachments` URL per shot.
  Upload every image/video through `~/.agents/skills/k-github/references/attachments.md`; that flow is the only source of embed URLs —
  `attach:` placeholders, fabricated URLs, and asking the user to drag files are all off limits.
  Uploading is a GitHub side effect and needs explicit approval. Keep local folder/filename mapping outside the body for upload resolution.
  Omit screenshots only for `not_applicable` or `explicitly_skipped`; not for `required` or `blocked`.
- Videos: embed each as a bare `user-attachments` URL alone in its own paragraph — GitHub renders a video player only then;
  players do not render inside markdown table cells or link/`<img>` syntax (verified: table cells degrade to text links).
  Per pair, stack it under a bold caption naming the covered behavior(s): a `Before:` line, blank line, before-video URL;
  then an `After:` line, blank line, after-video URL.
- Decision log: when a change embodies an externally visible decision (API shape, privilege model, error response, storage format, default), add `## Decisions` with `**<decision>** — risk: <what goes wrong if wrong>`.
  Omit for internal implementation-only choices.
- Link issues explicitly: `Closes #X` only when merging should close the issue, `Addresses #X` otherwise.
  Use only issue numbers verified to exist.

## General template

```markdown
Closes #X | Addresses #X

## Summary

-

## Test Plan

-

## Screenshots

<!-- UI-facing changes only; omit otherwise. One titled block per captured shot, uploaded via the browser-assisted flow and embedded by URL. -->

**<caption — static visual change>:**

Before:

<img src="https://github.com/user-attachments/assets/<uuid>" alt="<caption> (before)" />

After:

<img src="https://github.com/user-attachments/assets/<uuid>" alt="<caption> (after)" />

**<caption — behavior with a sequence of actions or interactivity>:**

Before:

https://github.com/user-attachments/assets/<uuid>

After:

https://github.com/user-attachments/assets/<uuid>
```
