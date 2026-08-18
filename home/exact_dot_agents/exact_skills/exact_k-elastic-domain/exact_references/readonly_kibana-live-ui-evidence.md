# Kibana Live UI Overlay — Evidence & Conduct

Companion to `kibana-live-ui.md` (the Kibana live UI target packet); load both together.
This file carries the worker conduct and evidence contract: safety boundary, screenshot handoff, live feedback overlay, and controller validation.

## Safety boundary

- Verification only: no repo edits, GitHub mutations, git writes, commits, pushes, or decisions.
- Never use ApplyPatch or file-editing tools.
- Write files only as Playwriter artifacts under `/tmp`, including focused screenshots;
  store each screenshot/pair/set in its own distinct `/tmp/<folder-name>/` directory rather than loose directly in `/tmp`.
- Mutating local/dev runtime data via Playwriter actions, local Kibana APIs, Dev Tools Console, or local Elasticsearch API calls is allowed for verification after target readiness/identity is established.
- Mutate only that local/dev runtime data; production, shared cloud, GitHub, git, repo files, committed files, labels, reviews, comments, branches, and user-visible external state stay untouched.
- Runtime data mutations must be local/dev-only, focused, named in the evidence, tied to the exact target/Elasticsearch endpoint used, and cleaned up or reported.
- Surface ES/Kibana runtime environment changes and service restarts as `Blocked` instructions for the user to apply, then continue in a later run after reload; applying or restarting from this worker is out of scope.
- If target identity is ambiguous or appears non-local/non-dev, return `Blocked` instead of mutating.

## Screenshot handoff

- Capture screenshots whenever the generic `live-ui-review` contract requires them for UI findings that may become review feedback.
  Otherwise capture screenshots only when they materially improve a candidate finding or blocker.
  For pre-navigation blockers, record why no screenshot exists.
- Store screenshots as Playwriter artifacts in a distinct `/tmp/<folder-name>/` directory —
  one dedicated folder per single screenshot, per comparison pair (base + PR/head), or per grouped set;
  each folder holds exactly its own set, kept out of loose `/tmp` and separate from unrelated sets.
  Use descriptive names and preserve handoff files.
- For each screenshot, record:
  - folder + local file path
  - description
  - target classification: PR/head, base, or both selected targets
  - exact URL
  - linked candidate/finding
  - suggested review comment placement
  - fidelity note for mocks or partial setup
- The screenshot handoff is for the controller's upload step only: no image uploads or local paths in GitHub review comments or bodies from this worker, and no extra comments solely for image paths; the controller uploads and embeds screenshots via the browser-assisted upload flow in `~/.agents/skills/k-github/references/attachments.md` behind explicit user approval.
- Proof-mode (`k-ui-capture`) stores each visual criterion's proof set in its own distinct `/tmp/<folder-name>/` folder (e.g. `/tmp/<topic>-<criterion-slug>/`) and hands the manifest to `k-compose-pr`; the files are embedded through that same explicitly approved upload flow.
  Uploading images and writing local paths into GitHub belongs to the controller alone, never to this worker.

## Live feedback overlay

When the user wants to point at specific real Kibana UI elements, use `,artifact live` after Playwriter has verified the registry-resolved local/dev `kbn_url`.

- Load and follow `~/.agents/skills/k-artifact/SKILL.md`.
- Use `,artifact live script <name>` and inject the returned JavaScript through Playwriter's page-evaluation capability.
- Tell the user capture is armed.
  The overlay intercepts page clicks until paused, uses Shadow DOM, and can be removed without changing the app.
- Keep `,artifact poll <name>` running and treat returned `source: live-overlay` items as user-guided live UI feedback.
- Preserve the screenshot handoff path for async review, visual comparison, or cases where live injection is blocked.

## Controller validation for Kibana overlay

Reject and rerun any `live-ui-review` result for this overlay that:

- reports only generic localhost probing
- omits any selected exact target URL
- uses WebFetch or shell/HTTP probes as readiness evidence
- skips Playwriter target checks
- claims targets are unavailable without showing the exact target/preflight evidence above
- omits the selected `target_packet` / overlay source
- uses browser/route/network mocks for a data-dependent UI finding without first attempting or explicitly ruling out faithful local/dev data setup through existing data, local Kibana/Elasticsearch APIs, or Kibana Dev Tools Console
- uses browser/route/network mocks when faithful verification is blocked by a required ES/Kibana runtime environment change;
  that must be returned as `Blocked` with setup instructions instead
- returns `Blocked` citing a missing/un-started `,kbn-stack` (no `ready:true` registry entry) in a shell-capable harness, instead of starting it with `,kbn-stack --detach` and continuing (Rung 0); rerun after the stack is started
- lists screenshot artifacts without local paths, descriptions, target URL/branch, or linked candidate/finding placement
- omits applicability, exact URLs checked, browser preflight status, readiness result for each target, branch/runtime evidence, comparison evidence for each checked candidate, UI evidence artifact manifest or `none`, page cleanup/owned-page URLs, and blockers/uncertainty

Accept without rerun a result that reports a valid Playwriter harness blocker:

- read-only/Ask-mode blocked Playwriter
- every selected exact browser target URL was attempted or explicitly blocked before navigation
- repeated reload/same-URL/same-snapshot loop was detected within the readiness stability guard
