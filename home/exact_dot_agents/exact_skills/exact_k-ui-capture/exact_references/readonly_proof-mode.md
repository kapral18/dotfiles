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
  - `met` — the built UI reaches and matches the intended visual/state/behavior, with a captured screenshot as evidence
  - `unmet` — the built UI does not match, with the observed state or behavior, the mismatch, and a screenshot
  - `blocked` — the state could not be reached, with the exact blocker from the shared ladder (missing runtime, runtime prerequisite, unsafe data setup)

## Proof capture

- Categorize each changed observed behavior by interactivity: a static visual change is proven by before/after screenshots;
  a behavior involving a sequence of actions or interactivity is proven by short before/after videos (Playwright `recordVideo`, see the Video Recording section of `~/.agents/skills/k-playwriter/SKILL.md`).
- Follow the shared Screenshot & evidence capture rules.
  Store each visual/UI criterion's proof set as Playwriter artifacts in its own distinct `/tmp/<folder-name>/` folder with descriptive filenames — never combine unrelated criteria/sets in one folder.
- Capture the smallest set that proves each visual/UI criterion — the key state(s) the intended behavior describes, not every navigation.
- For each shot, record a manifest entry: its folder, filename, caption (what it proves), exact URL, the linked acceptance criterion or visual goal, and any fidelity note (mocked/partial data).
- The manifest and the `/tmp` paths are a handoff to the caller for the upload step only.
  Leave uploading and embedding to the publication step, which uses the browser-assisted upload flow in `~/.agents/skills/k-github/references/attachments.md` behind explicit user approval; keep images and local paths out of PR bodies/comments during this proof phase.

## Return exactly

- `applicability`: applicable / not applicable, with changed-path evidence
- `target_packet`: selected packet name/source, including overlay source when an overlay supplied it
- `urls_checked`: the exact runtime-under-verification URL(s), or an explicit blocker before navigation
- `browser_preflight`: Playwriter and its completed preflight, or why it could not run
- `target_readiness`: readiness result for each URL from Playwriter evidence

- `branch_evidence`: branch/runtime identity evidence, or what could not be verified
- `data_setup`: existing data checked, local/dev data seeded/mutated, cleanup result, or exact data/mutation still needed
- `criteria_verdicts`: per intended visual/UI criterion, `met` / `unmet` / `blocked` with the linked screenshot and observed state
- `screenshot_manifest`: `none`, or the list of proof entries (folder, filename, caption, URL, linked criterion, fidelity note)
- `pages`: pages created and closed, or URLs left open
- `blockers_or_uncertainty`: none, or precise blockers/remaining uncertainty
