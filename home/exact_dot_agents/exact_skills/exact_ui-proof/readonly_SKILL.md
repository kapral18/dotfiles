---
name: ui-proof
description: "Use when verifying that a built or changed UI matches its intended visual and capturing screenshot proof for a PR — during feature building (/build) or PR composition (compose-pr). Head-only; not for reviewing others' changes."
---

# UI Proof

Head-only live-UI verification that a **built or changed** UI matches its **intended visual**, capturing the screenshot set that proves it for a PR.
This is the creation-side sibling of `live-ui-review.md`: same runtime machinery, opposite direction.
`live-ui-review` compares PR/head against base to find regressions for `/agent-review` to judge;
`ui-proof` checks the built runtime against the intended visual and captures proof to attach to a PR.

Load `~/.agents/skills/agent-review/references/live-ui-runtime.md` for the shared runtime contract:
mode boundary, terminology, target-packet resolution, Playwriter preflight, readiness stability guard, screenshot & evidence capture, runtime-start rung, data/setup ladder, and the hard runtime constraints.
This file adds only the proof-mode specifics: the head-only model, the intended-visual oracle, and the proof return shape.

## Do not use

- reviewing an existing PR or someone else's changes, or hunting regressions:
  `~/.agents/skills/review/SKILL.md` / `/agent-review` (which owns `live-ui-review`)
- a change with no UI/runtime surface: there is nothing to prove visually — skip
- generic browser automation with no intended-visual to check against: `~/.agents/skills/playwriter/SKILL.md` directly

## Execution model

`ui-proof` runs **inline** in its caller, which already holds Playwriter and local/dev mutation permissions:

- `/build` — a phase after the mechanical gates verifies any acceptance criterion whose evidence is visual (see the `build` skill).
- `compose-pr` — captures/embeds proof at PR-composition time when the diff is UI-facing and no `/build` manifest exists.
- ad-hoc — fired directly when the user asks to verify a UI and capture screenshots.

It is not a `/agent-review` read-only reviewer lane and needs no isolated subagent profile;
the shared read-only constraints still bind everything except Playwriter/browser commands and packet-permitted local/dev data setup.

## Caller supplies

- the built/changed worktree path and branch/sha (the runtime under verification)
- changed UI paths
- the **intended visual** to check against — exactly one of:
  - a spec acceptance criterion tagged `judgment:` whose evidence is visual (`/build`)
  - a linked issue/design mockup, screenshot, or the PR's stated visual goal (`compose-pr`)
  - the user's described target (ad-hoc)
- selected target packet, including overlay source when an overlay supplied it (`elastic/kibana` → `~/.agents/skills/elastic-domain/references/kibana-live-ui.md`)
- required runtime config (feature-flag/settings the path needs to be reachable), or an empty set
- the `/tmp` output location: each visual criterion's proof set goes in its own distinct `/tmp/<folder-name>/` folder (never a single shared dump), named for the criterion — e.g. `/tmp/<topic>-<criterion-slug>/`

## Applicability

Decide whether the changed paths touch UI/runtime behavior and whether an intended visual exists to check against.

- If the change has no UI/runtime surface, return `Not applicable` with the changed-path evidence.
- If UI changed but the caller supplied no intended visual, return `Blocked`: proof needs an oracle (which visual state counts as correct).
  Name what is missing.
- Do not return `Not applicable` because the runtime has no data. Missing data is setup work or `Blocked` per the shared data/setup ladder.

## Head-only model

- There is no base comparison: a newly built visual has no base counterpart, and proof is about matching the intended state, not diffing against `main`.
- Verify only the runtime under verification. Never navigate or start a base/main runtime.
- The oracle is the intended visual, not a base screenshot: reach the target state, observe it, and judge whether it matches the intended visual the caller supplied.
- Per visual criterion, return a verdict:
  - `met` — the built UI reaches and matches the intended visual, with a captured screenshot as evidence
  - `unmet` — the built UI does not match, with the observed state, the mismatch, and a screenshot
  - `blocked` — the state could not be reached, with the exact blocker from the shared ladder (missing runtime, runtime prerequisite, unsafe data setup)

## Proof capture

- Follow the shared Screenshot & evidence capture rules.
  Store each visual criterion's proof set as Playwriter artifacts in its own distinct `/tmp/<folder-name>/` folder with descriptive filenames — never combine unrelated criteria/sets in one folder.
- Capture the smallest set that proves each visual criterion — the key state(s) the intended visual describes, not every navigation.
- For each shot, record a manifest entry: its folder, filename, caption (what it proves), exact URL, the linked acceptance criterion or visual goal, and any fidelity note (mocked/partial data).
- The manifest and the `/tmp` paths are a handoff to the caller and the user only.
  Do not upload images or put local paths in a PR body/comment; the user attaches the files to the PR (see `compose-pr`).

## Return exactly

- `applicability`: applicable / not applicable, with changed-path evidence
- `target_packet`: selected packet name/source, including overlay source when an overlay supplied it
- `urls_checked`: the exact runtime-under-verification URL(s), or an explicit blocker before navigation
- `playwriter_preflight`: whether the Playwriter skill was loaded and `playwriter skill` was run; if not, why
- `target_readiness`: readiness result for each URL, from Playwriter evidence
- `branch_evidence`: branch/runtime identity evidence, or what could not be verified
- `data_setup`: existing data checked, local/dev data seeded/mutated, cleanup result, or exact data/mutation still needed
- `criteria_verdicts`: per intended-visual criterion, `met` / `unmet` / `blocked` with the linked screenshot and observed state
- `screenshot_manifest`: `none`, or the list of proof entries (folder, filename, caption, URL, linked criterion, fidelity note)
- `pages`: pages created and closed, or URLs left open
- `blockers_or_uncertainty`: none, or precise blockers/remaining uncertainty
