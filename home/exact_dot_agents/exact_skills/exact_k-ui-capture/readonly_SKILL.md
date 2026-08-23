---
name: k-ui-capture
description: "Use when proving UI visual/behavior, auditing a diff for capturable changes, or capturing/uploading pre/post PR screenshots/videos."
---

# UI Capture

The creation-side live-UI proof skill: verify a **built or changed** UI against its **intended visual, state, or behavior**, capture the before/after screenshots and videos that prove it, and (when asked) upload them to GitHub.
This is the creation-side sibling of `live-ui-review.md`: same runtime machinery, opposite direction.
`live-ui-review` compares PR/head against base to find regressions for `/k-deep-review` to judge;
this skill proves the built runtime matches its intent.

The mechanics live in one shared contract — load `~/.agents/skills/k-ui-capture/references/proof-mode.md` and follow it end to end:
caller inputs, applicability, the head-only model, proof capture, and the exact return shape.
`/k-build`'s live-UI proof phase and `k-compose-pr`'s publication packet load that reference directly;
this entrypoint owns routing and the two direct entries below.

Other shared cores, loaded when their step applies:

- runtime targets, Playwriter preflight, readiness, data/setup ladder: loaded by the proof-mode contract via `~/.agents/skills/k-review/references/live-ui-runtime.md`
- video recording mechanics: the Video Recording section of `~/.agents/skills/k-playwriter/SKILL.md`
- pre-upload QA, browser-assisted upload, and markdown embedding rules: `~/.agents/skills/k-github/references/attachments.md`

## Out of scope (use the named alternative)

- reviewing an existing PR or someone else's changes, or hunting regressions:
  `~/.agents/skills/k-review/SKILL.md` / `/k-deep-review` (which owns `live-ui-review`)
- a change with no UI/runtime surface: there is no UI proof to capture — skip
- generic browser automation with no intended UI state/behavior to check against: `~/.agents/skills/k-playwriter/SKILL.md` directly

## Entry selection

Pick exactly one entry from what the request supplies:

- **Direct verify** — the user names the target and intended visual/behavior ("verify this UI and screenshot it").
  Skip the audit: run the proof-mode contract with the user's described target as the oracle. Steps 3-5 apply; upload only when asked.
- **Diff audit** — the user wants UI changes discovered and proven ("capture media proof for this diff/PR"). Run steps 1-5 in order.

## Step 1 — Audit the diff for capturable UI changes

Inspect the change set and itemize what can be visually proven:

1. Resolve the diff: `git diff origin/<base>...HEAD` plus staged/unstaged working-tree changes, or `gh pr diff <n>` when a PR is named.
2. Load `~/.agents/skills/k-ui-capture/references/proof-mode.md` and build its Behavior inventory:
   apply the split test (one item per independently observable difference), the classification test (static state → screenshot pair;
   interactive sequence, timing, or continuous behavior → video pair), the coverage plan (dedicated pair per item by default;
   one shared pair when same-trigger items are each plainly visible in it), and the baseline test (`baseline` vs `intra-change` vs head-only) to every user-visible change.
   Mechanical, test-only, or non-rendered changes are not capture items.
3. When the diff has no user-visible surface, report `Not applicable` with the changed-file evidence and stop.

Completion criterion: every changed file is accounted for as part of an inventory item or explicitly excluded, every item carries its media classification, or a `Not applicable` verdict with evidence ends the run.

## Step 2 — Assemble the capture inputs

Build the exact inputs the proof-mode contract's Caller supplies section requires, per item:

- the built/changed worktree path and branch/sha, and the changed UI paths from Step 1
- the intended visual/UI state or behavior (the oracle), derived from the diff, linked issue/PR context, or the user's description;
  ask the user once when an item's oracle stays ambiguous after that
- the selected target packet and required runtime config, resolved as the proof-mode contract's Caller supplies section directs
- a distinct `/tmp/ui-capture-<item-slug>/` output folder per item, or per shared pair when the coverage plan consolidates items

Completion criterion: every item has a testable oracle and a complete input set, or the item is reported blocked with what is missing.

## Step 3 — Reuse check against published PR proof

When the target PR already exists, run the proof-mode contract's Existing published proof gate before any capture:
collect the PR's published before/after media, map each inventory item to the published pair conveying its contrast (shared pairs allowed per the coverage plan), and reuse a pair only when it passes both the adequacy check (media type matches the item's classification and that item's contrast is plainly visible) and the freshness check against the item's changed paths.
Reuse the URLs of passing pairs; carry every stale, inadequate, partial, or unmapped item into Step 4. Skip this step when no PR exists yet.

Completion criterion: every inventory item is classified `reused` with its existing URLs or routed to capture with the adequacy/staleness evidence.

## Step 4 — Capture via the proof-mode contract

Load `~/.agents/skills/k-ui-capture/references/proof-mode.md` and run it inline per item routed from Step 3.
It captures each item's proof set in the media type its inventory classification requires and returns the manifest.
For before/after pairs, its base-runtime exception covers capturing `before` presentation artifacts on the base branch.

Completion criterion: every routed item has a `met`/`unmet`/`blocked` verdict and manifest entries from the proof-mode contract.

## Step 5 — Gated upload and markdown

Load `~/.agents/skills/k-github/references/attachments.md` and follow it end to end:
pre-upload QA, the browser-assisted upload, and the presentation rules for embedding.
Upload only newly captured media; Step 3 supplies the URLs for reused pairs.
Build the proof-mode Claim map before drafting embed text: every behavior claim in the body/comment maps to an inventory item with an adequate asset; drop unmapped claims.
Place `baseline` pairs in the PR/issue body's main Screenshots/Videos section;
place `intra-change` pairs in a separate comment/thread when requested for reviewer re-verification.
Uploading is a GitHub side effect — show the QA summary, claim map, and destination, and wait for explicit user approval before uploading.
After upload, emit the ready-to-paste markdown block built per those presentation rules.

Completion criterion: new media uploaded and markdown emitted with a complete claim map, or local manifest paths returned with upload marked `pending_approval`/`skipped`.

## Deliverable

- `audit_summary`: capture items with classification and frame (`baseline` / `intra-change` / head-only), plus excluded files (diff-audit entry only)
- `proof_reuse`: per item, `reused` with existing URLs or the staleness evidence routing it to capture
- `capture_manifest`: the proof-mode manifest(s) and verdicts
- `claim_map`: every embed claim → inventory item → asset, or `n/a` when no embed drafted
- `upload_status`: `uploaded` with asset URLs, `pending_approval` with local paths, or `skipped`
- `markdown_snippet`: the final embed block, when uploaded
