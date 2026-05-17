---
name: fix-cursor-cli
description: Targeted repair skill for local Cursor CLI regressions (macOS quarantine/native-module policy failures and the `/model` empty-list OR duplicate-variant picker regression). Use when those symptoms are present.
disable-model-invocation: true
---

# Fix Cursor CLI

Diagnose first, then apply targeted repair.

## Use when

- `cursor-agent` shows macOS policy/quarantine native-module load failures
- `/model` is empty or shows `No matches` while `cursor-agent models` still lists available models
- `/model` shows thinking/non-thinking variants as duplicate entries with no `Thinking` suffix to distinguish them

## Do not use

- generic `cursor-agent` failures without quarantine or picker-state evidence
- account/permission/model-routing issues not caused by local bundle state
- routine model selection with no runtime symptoms
- non-Cursor CLI issues unrelated to `cursor` / `cursor-agent`

## Workflow

1. Reproduce and classify (do not fix yet):
   - `command -v cursor cursor-agent`
   - `cursor-agent --version`
   - `cursor-agent models`
   - if needed, reproduce interactive picker behavior (`/model`) in a fresh session
2. Read-only state check (preferred first step on any machine):
   - `bash ~/.agents/skills/fix-cursor-cli/scripts/fix_cursor_cli.sh --reason check`
   - Reports picker state per active bundle (`v2-good` / `v1-collapses-variants` / `old-empty-picker` / `unknown-shape`) and exits non-zero if any active bundle needs a fix.
3. Choose a targeted fix:
   - if evidence points to fresh-process startup failure with local bundle regression/quarantine signatures, run:
     - `bash ~/.agents/skills/fix-cursor-cli/scripts/fix_cursor_cli.sh --reason startup-failure`
   - if evidence is interactive-only (`/model` empty OR duplicate-variant entries in a fresh session while `cursor-agent models` succeeds), run:
     - `bash ~/.agents/skills/fix-cursor-cli/scripts/fix_cursor_cli.sh --reason empty-picker`
   - `--reason auto` (default) performs diagnosis (including bundle-state classification) and no-ops on healthy machines; prefer this when symptom classification is incomplete.
   - if the script is missing, run `chezmoi apply --no-tty` and retry
   - only use manual bundle edits when the bundled script is unavailable or provably insufficient
4. Re-verify end-to-end:
   - `cursor-agent models` succeeds
   - `--reason check` reports `Check OK`
   - `/model` shows entries (and `Thinking` suffix on variant entries) in a fresh interactive session
5. If the script reports `unknown shape` and dumps anchor context:
   - Cause: upstream cursor-cli bundle shape changed since this skill was last updated.
   - Recovery (do not retry the script blindly):
     1. Read the printed anchor-context block. It shows the current minified code
        around the picker call (`useModelParameters:!0,doNotUseMarkdown:!0`).
     2. Identify the as-shipped buggy form (an `A.some((...parameterDefinitions...))?A:void 0` expression, where `A` is whichever single-letter var the minifier chose for the filtered-models list).
     3. Update the regex patterns in `scripts/picker_patch.py`:
        - The existing `PATTERN_OLD` / `PATTERN_V1` / `PATTERN_V2` are already var-name-agnostic and use named groups (`A`/`B`/`C`/`D`/`E`/`F`). Only update them if the structural shape of the code (not the variable letters) has changed.
        - Add a new pattern alongside the existing ones if upstream introduced a new arrangement.
        - The `_build_v2()` helper handles synthesizing the patched form from the captured group names; reuse it when adding new patterns.
     4. Re-run with `--reason check` first to confirm classification, then `--reason empty-picker`.
   - Both `scripts/fix_cursor_cli.sh` and `scripts/picker_patch.py` document the bug semantics in their headers; read them before editing.
6. Share learning:
   - state what symptom was detected, what fix was chosen, and what bundle state the script reported (v2-good / v1-collapses-variants / old-empty-picker / unknown-shape)

## Assets

- `scripts/fix_cursor_cli.sh`: diagnose-first orchestrator. Probes `cursor-agent`, checks quarantine attrs, invokes `picker_patch.py` for picker-state classification and patching, and reports a clear per-bundle summary. Supports `--reason check` for a read-only audit that exits non-zero if anything needs fixing.
- `scripts/picker_patch.py`: var-name-agnostic regex classifier and migrator for the model-picker bundle. Handles the three known states (`old-empty-picker` -> V2, `v1-collapses-variants` -> V2, `v2-good` no-op) across all webpack chunks containing the picker code, and dumps anchor context for unknown shapes.

## Output requirements

- Lead with diagnosis (including the picker bundle state per active file) and confidence level.
- Include evidence for the chosen path (commands/results, not guesses).
- State whether `fix_cursor_cli.sh` changed anything and what worst-state was observed before/after (`v2-good` / `v1-collapses-variants` / `old-empty-picker` / `unknown-shape`).
- If interactive verification cannot be automated, ask the user to confirm `/model` after restart.

## Constraints

- Evidence-first: verify before and after each remediation step using `--reason check`.
- Do not run repair steps preemptively on healthy machines.
- Prefer the bundled skill assets (`fix_cursor_cli.sh` + `picker_patch.py`) over ad-hoc manual edits.
- Treat fixes as machine-local and temporary; re-evaluate on each host/update.
