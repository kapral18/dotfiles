# Proof-Mode Contract (shared)

The proof-mode live-UI contract: head-only verification that a built/changed UI matches its intended visual, state, or behavior, and capture of the proof set for a PR.
Loaded by the `k-ui-capture` skill (direct entry), `/k-build`'s live-UI proof phase, and `k-compose-pr`'s publication packet;
the caller owns routing and supplies the inputs below.

Load `~/.agents/skills/k-review/references/live-ui-runtime.md` for the shared runtime contract:
mode boundary, terminology, target-packet resolution, Playwriter preflight, readiness stability guard, screenshot & evidence capture, runtime-start rung, data/setup ladder, and the hard runtime constraints.
This file adds only the proof-mode specifics: the head-only model, the intended UI state/behavior oracle, and the proof return shape.

This contract runs **inline** in its caller, which already holds Playwriter and local/dev mutation permissions.
It is not a `/k-deep-review` read-only reviewer lane and needs no isolated subagent profile;
the shared read-only constraints still bind everything except Playwriter commands and packet-permitted local/dev data setup.

## Caller supplies

- the built/changed worktree path and branch/sha (the runtime under verification)
- changed UI paths
- the **intended visual/UI state or behavior** to check against — exactly one of:
  - a spec acceptance criterion tagged `judgment:` whose evidence is visual (`/k-build`)
  - a linked issue/design mockup, screenshot, UI behavior repro, or the PR's stated UI goal (`k-compose-pr`)
  - the user's described target, or the diff-derived intended delta confirmed with the user (`k-ui-capture`)
- selected target packet, including overlay source when an overlay supplied it (`elastic/kibana` → `~/.agents/skills/k-elastic-domain/references/kibana-live-ui.md`)
- required runtime config (feature-flag/settings the path needs to be reachable), or an empty set
- the `/tmp` output location: each visual/UI criterion's proof set goes in its own distinct `/tmp/<folder-name>/` folder (never a single shared dump), named for the criterion — e.g. `/tmp/<topic>-<criterion-slug>/`

## Applicability

Decide whether the changed paths touch UI/runtime behavior and whether an intended visual/UI state or behavior exists to check against.

- If the change has no UI/runtime surface, return `Not applicable` with the changed-path evidence.
- If UI changed but the caller supplied no intended visual/UI state or behavior, return `Blocked`:
  proof needs an oracle (which visible state or interaction result counts as correct). Name what is missing.
- A runtime with no data is still applicable: missing data is setup work or `Blocked` per the shared data/setup ladder, never `Not applicable`.

## Head-only model

- There is no base comparison: a newly built UI state/behavior has no base counterpart, and proof is about matching the intended state or behavior, not diffing against `main`.
- Verify only the runtime under verification. Never navigate or start a base/main runtime for the verdict.
  Exception: a base runtime may be used solely to capture `before` presentation artifacts for a PR's before/after pairs;
  those feed publication, never the verdict.
- The oracle is the intended visual/UI state or behavior, not a base screenshot:
  reach the target state, observe it, and judge whether it matches the intended state or behavior the caller supplied.
- For UI behavior bugs whose success is not fully visible (clipboard contents, keyboard/focus behavior, downloaded files, network effects), capture the smallest visible proof around the interaction — for example the target control before action and success/error state after action — and record the non-visual assertion in the verdict.
- Per visual/UI criterion, return a verdict:
  - `met` — the built UI reaches and matches the intended visual/state/behavior, with the captured proof media (screenshot or video per the item's classification) as evidence
  - `unmet` — the built UI does not match, with the observed state or behavior, the mismatch, and the captured media
  - `blocked` — the state could not be reached, with the exact blocker from the shared ladder (missing runtime, runtime prerequisite, unsafe data setup)

## Behavior inventory and media requirements

Build this inventory before the published-proof gate and before any capture; both consume it.

1. **Split test — one item per behavior.**
   Enumerate every independently observable difference a user can see or trigger; each one is its own inventory item.
   Two observable differences stay two items even when one diff, commit, or feature produced both — could one ship without the other?
   Then split.
   A caption that needs "and", "plus", a semicolon, or a parenthetical to name a second observable difference is naming a second item.
2. **Classification test — screenshot vs video.** Classify by what the fix changes, not by the setup action needed to reach the state:
   - static state — the changed surface is fully visible in one settled rendered state: before/after screenshot pair.
     Setup actions may happen off-camera before the screenshot, such as opening a menu, command palette, popover, or modal.
     If the fix changes only that opened surface's static styling, copy, layout, visibility, or contrast, keep it screenshot-classified.
   - interactive sequence — the fixed behavior is the action sequence itself, the transition/result across time, or a single behavior that needs multiple states to be understood: short before/after video pair (Playwright `recordVideo`, see the Video Recording section of `~/.agents/skills/k-playwriter/SKILL.md`).
     The video drives the same trigger on both sides — before: perform the action, show the old outcome; after:
     repeat it, show the new outcome.
   - Multi-state proof without action semantics can use a small ordered screenshot set when that conveys the behavior clearly;
     use video only when the sequence, timing, or continuous interaction is the fixed functionality or screenshots would not carry the claim.
3. **Coverage plan — items to assets.** Each item gets its own dedicated pair by default.
   Consolidate into one shared pair only when several items are observed through the same trigger on the same target and that single pair plainly shows each item's before/after contrast in the same frames; the shared pair's caption then names every covered behavior.
   Capture each distinct interaction exactly once — re-recording the same interaction to make a second, visually identical pair is duplication, not extra rigor.
4. **Sufficiency test — judged per item, per asset.**
   An asset covers an item only when that item's delta is plainly visible in it; covering one behavior never implies covering another.
   A pair too small, cropped, or static to convey any covered item's contrast proves nothing, regardless of how clean it looks.
5. **Baseline test — comparison frame.** Tag each item with exactly one frame:
   - `baseline` — the user-visible product delta vs the PR/integration base (or last shipped behavior).
     Before = that base when the base can show the old outcome; after = the runtime under verification.
   - `intra-change` — a delta between two tips on the same change branch (a mid-change regression and its fix).
     Before = earlier tip; after = later tip.
     Use this only when a human needs visual proof of that mid-change fix; it is a separate proof class from the product delta vs base.
     When the base never reaches the old state (capability absent on base), keep the item as head-only proof of the new capability, or as `intra-change` when comparing two branch tips.
     Capture only before-states the chosen frame can actually produce.
     Publication channel: `baseline` pairs embed in the PR/issue body's main Screenshots/Videos section;
     `intra-change` pairs publish in a separate comment/thread when requested for reviewer re-verification, and stay out of the body's main before/after section so they are not read as base↔head.
6. **Claim map — prose ⊆ assets.**
   Before drafting embed markdown or editing a PR/issue body/comment that cites proof, list every behavior claim the text will make and the inventory item + asset that proves it.
   Emit the embed only when every claim has an adequate mapped asset (sufficiency test).
   Drop or demote any claim that lacks one; covering one item never licenses claiming another.

## Existing published proof gate

When the caller's target is an existing PR that may already carry published proof, run this gate before capturing anything.
Skip it when no PR exists yet (for example `/k-build` ahead of publication).

1. Collect published proof: read the PR body and every comment (`gh pr view <n> --json body,comments`), and list each published proof block — `## Screenshots` sections, `user-attachments` image/video URLs, and their captions — with the container's `createdAt`/`updatedAt`.
2. Map each inventory item to the published pair that conveys its contrast, by caption and behavior.
   Several items may share one pair when they meet the coverage plan's consolidation conditions;
   an item with only one side published, or with no pair conveying its contrast, goes to capture.
3. Adequacy check per mapped item: the pair's media type must match the item's classification, that item's specific before/after contrast must be plainly visible in the pair (sufficiency test, judged per item), and the pair's comparison frame must match the item's baseline-test tag (`baseline` vs `intra-change`).
   A screenshot pair mapped to a video-classified item is inadequate regardless of freshness — route it to capture.
   A body-section base↔head pair never satisfies an `intra-change` item, and an intra-change tip↔tip pair never satisfies a `baseline` item.
4. Freshness check per adequate item: treat the pair as current only when no commit newer than the container's `createdAt` touches the item's changed UI paths (`git log --since=<createdAt> <base>..HEAD -- <paths>`), and the base branch has not advanced over commits touching those same paths since the `before` capture.
   Treat an ambiguous timestamp or mapping as stale.
5. Reuse pairs that pass both checks: carry their existing `user-attachments` URLs into the caller's embed step and skip capture and upload for those items.
   Recapture every stale, inadequate, partial, or unmapped item through the sections below, and upload only the new media.

## Capture hygiene

Apply on every capture run (any repo):

1. **Identity bind.**
   Keep shell cwd, topic-spec, and recorder scripts pointed at the runtime under verification;
   use absolute paths for `/tmp` recorders and worktree roots when switching tips.
2. **Control resolution.**
   Resolve click/type targets from the live page's accessible name, role, and stable test id before recording;
   when an assumed label times out, re-probe the live a11y tree once and use the observed name.
3. **Evidence retention.**
   Leave toasts, banners, dialogs, and warnings that constitute the item's delta visible through the clip;
   dismiss them only after that item's capture finishes.
4. **Tip ordering.**
   Finish every after-clip for tip A before swapping tree/runtime state to tip B for before-clips (or the reverse planned order);
   keep each tip's batch complete under that tip's tree.
5. **Clip focus.**
   Start published clips at the proving interaction; trim login, welcome, and idle load lead-in before pre-upload QA (see the Video Recording section of `~/.agents/skills/k-playwriter/SKILL.md`).
6. **Isolation.**
   Run capture as its own workstream: finish or park unrelated merges, history rewrites, and CI-fix churn before starting recorders so the worktree under the camera stays the intended tip.

## Proof capture

- Capture per the coverage plan: each distinct interaction/state once, in the media type its classification requires;
  a shared pair lists every covered item in its manifest entry and caption.
- Follow Capture hygiene and the shared Screenshot & evidence capture rules.
  Store each visual/UI criterion's proof set as Playwriter artifacts in its own distinct `/tmp/<folder-name>/` folder with descriptive filenames — never combine unrelated criteria/sets in one folder.
- Capture the smallest set that proves each visual/UI criterion — the key state(s) the intended behavior describes, not every navigation.
- For each captured asset (screenshot or video), record a manifest entry: its folder, filename, media type, frame (`baseline` / `intra-change` / `head-only`), caption (what it proves), exact URL, the linked acceptance criterion or visual goal, and any fidelity note (mocked/partial data).
- The manifest and the `/tmp` paths are a handoff to the caller for the upload step only.
  Leave uploading and embedding to the publication step, which uses the browser-assisted upload flow in `~/.agents/skills/k-github/references/attachments.md` behind explicit user approval; keep images and local paths out of PR bodies/comments during this proof phase.
  When the caller drafts embed text, require the Claim map (inventory item 6) before approval.

## Return exactly

- `applicability`: applicable / not applicable, with changed-path evidence
- `target_packet`: selected packet name/source, including overlay source when an overlay supplied it
- `urls_checked`: the exact runtime-under-verification URL(s), or an explicit blocker before navigation
- `browser_preflight`: Playwriter and its completed preflight, or why it could not run
- `target_readiness`: readiness result for each URL from Playwriter evidence

- `branch_evidence`: branch/runtime identity evidence, or what could not be verified
- `data_setup`: existing data checked, local/dev data seeded/mutated, cleanup result, or exact data/mutation still needed
- `criteria_verdicts`: per intended visual/UI criterion, `met` / `unmet` / `blocked` with the linked proof media and observed state
- `published_proof`: per item, `reused` with the existing URLs and container evidence, `stale` or `inadequate_media` with the reason, or `none_published`; `skipped` when no PR exists yet
- `proof_manifest`: `none`, or the list of proof entries (folder, filename, media type, frame, caption, URL, linked criterion, fidelity note)
- `claim_map`: `n/a` when no embed is drafted; otherwise every behavior claim in the draft paired with its inventory item and proving asset, with zero unmapped claims
- `pages`: pages created and closed, or URLs left open
- `blockers_or_uncertainty`: none, or precise blockers/remaining uncertainty
