---
name: k-ui-capture
description: "Use when proving UI visual/behavior, auditing a diff for capturable changes, or capturing/uploading pre/post PR screenshots/videos."
---

# UI Capture

The creation-side live-UI proof skill: verify a **built or changed** UI against its **intended visual, state, or behavior**, capture the before/after screenshots and videos that prove it, and (when asked) upload them to GitHub.
This is the creation-side sibling of `live-ui-review.md`: same runtime machinery, opposite direction.
`k-agent-live-ui-review` compares PR/head against base to find regressions for `/k-deep-review` to judge;
this skill proves the built runtime matches its intent.

The mechanics live in one shared contract — load `~/.agents/skills/k-ui-capture/references/proof-mode.md` and follow it end to end:
caller inputs, applicability, the head-only model, proof capture, and the exact return shape.
`/k-build`'s live-UI proof phase and `k-compose-pr`'s publication packet load that reference directly;
this entrypoint owns routing and the two direct entries below.

## Non-Skippable Publication Gate

Before any upload or PR/issue body/comment edit:

1. Load `~/.agents/skills/k-ui-capture/references/proof-mode.md`.
2. Produce the proof-mode return shape through `claim_map`.
3. Proceed only when the target publication text has zero unmapped behavior claims.

When the proof-mode return shape is missing, return `upload_status: skipped` or `pending_approval` and leave PR/issue body/comment media unchanged.
Use only proof-mode captured or reused assets in this flow; classify synthetic clips, test-result clips, and prose caveats as inadequate publication assets.

Other shared cores, loaded when their step applies:

- runtime targets, Playwriter preflight, readiness, data/setup ladder: loaded by the proof-mode contract via `~/.agents/skills/k-review/references/live-ui-runtime.md`
- video recording mechanics: before recording, load and follow `~/.agents/skills/k-playwriter/references/video-recording.md` in full
- pre-upload QA, browser-assisted upload, and markdown embedding rules: `~/.agents/skills/k-github/references/attachments.md`

## Out of scope (use the named alternative)

- reviewing an existing PR or someone else's changes, or hunting regressions:
  `~/.agents/skills/k-review/SKILL.md` / `/k-deep-review` (which owns `k-agent-live-ui-review`)
- a change with no UI/runtime surface: there is no UI proof to capture — skip
- generic browser automation with no intended UI state/behavior to check against: `~/.agents/skills/k-playwriter/SKILL.md` directly

## Entry selection

Pick exactly one entry from what the request supplies:

- **Direct verify** — the user names the target and intended visual/behavior ("verify this UI and screenshot it").
  Skip the audit: run the proof-mode contract with the user's described target as the oracle. Steps 3-5 apply; upload only when asked.
- **Diff audit** — the user wants UI changes discovered and proven ("capture media proof for this diff/PR"). Run steps 1-5 in order.

## Steps 1–2 — Audit the diff and assemble capture inputs

For the Diff audit entry, before inspecting the diff or assembling its capture inputs, read and follow `~/.agents/skills/k-ui-capture/references/diff-audit.md` in full.
Follow both completion criteria before Step 3. The Direct verify entry skips these steps as specified above.

## Step 3 — Reuse check against published PR proof

When the target PR already exists, run the proof-mode contract's Existing published proof gate in full before any capture.
Carry reused URLs forward; route all other inventory items to Step 4. Skip this step when no PR exists yet.

Completion criterion: every inventory item is classified `reused` with its existing URLs or routed to capture with the adequacy/staleness evidence.

## Step 4 — Capture via the proof-mode contract

Load `~/.agents/skills/k-ui-capture/references/proof-mode.md` and run it inline per item routed from Step 3.
It captures each item's proof set in the media type its inventory classification requires and returns the manifest.
For before/after pairs, its base-runtime exception covers capturing `before` presentation artifacts on the base branch.

Completion criterion: every routed item has a `met`/`unmet`/`blocked` verdict and manifest entries from the proof-mode contract.

## Step 5 — Gated upload and markdown

Before preparing an upload or embed markdown, read and follow `~/.agents/skills/k-ui-capture/references/upload-and-markdown.md` in full.
Upload only when asked and explicitly approved or covered by a workflow-defined approval packet;
otherwise return local manifest paths with `pending_approval`/`skipped`.

## Deliverable

- `audit_summary`: capture items with classification and frame (`baseline` / `intra-change` / head-only), plus excluded files (diff-audit entry only)
- `proof_reuse`: per item, `reused` with existing URLs or the staleness evidence routing it to capture
- `capture_manifest`: the proof-mode manifest(s) and verdicts
- `claim_map`: every embed claim → inventory item → asset, or `n/a` when no embed drafted
- `upload_status`: `uploaded` with asset URLs, `pending_approval` with local paths, or `skipped`
- `markdown_snippet`: the final embed block, when uploaded
