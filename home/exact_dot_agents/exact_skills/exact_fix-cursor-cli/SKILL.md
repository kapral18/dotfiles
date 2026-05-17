---
name: fix-cursor-cli
description: Targeted repair skill for two local Cursor CLI regressions (macOS quarantine/native-module policy failures and the known `/model` empty-list picker regression). Use when those symptoms are present.
disable-model-invocation: true
---

# Fix Cursor CLI

Diagnose first, then apply targeted repair.

## Use when

- `cursor-agent` shows macOS policy/quarantine native-module load failures
- `/model` is empty or shows `No matches` while `cursor-agent models` still lists available models

## Do not use

- generic `cursor-agent` failures without quarantine or empty-picker evidence
- account/permission/model-routing issues not caused by local bundle state
- routine model selection with no runtime symptoms
- non-Cursor CLI issues unrelated to `cursor` / `cursor-agent`

## Workflow

1. Reproduce and classify (do not fix yet):
   - `command -v cursor cursor-agent`
   - `cursor-agent --version`
   - `cursor-agent models`
   - if needed, reproduce interactive picker behavior (`/model`) in a fresh session
2. Collect concrete failure evidence:
   - crash text, policy/quarantine errors, command output, and whether issue is interactive-only
3. Choose a targeted fix:
   - if evidence points to fresh-process startup failure with local bundle regression/quarantine signatures, run:
     - `bash ~/.agents/skills/fix-cursor-cli/scripts/fix_cursor_cli.sh --reason startup-failure`
   - if evidence is interactive-only (`/model` empty in fresh session while `cursor-agent models` succeeds), run:
     - `bash ~/.agents/skills/fix-cursor-cli/scripts/fix_cursor_cli.sh --reason empty-picker`
   - `--reason auto` (default) performs diagnosis and no-ops on healthy machines; prefer this when symptom classification is incomplete.
   - if the script is missing, run `chezmoi apply --no-tty` and retry
   - only use manual bundle edits when the bundled script is unavailable or provably insufficient
4. Re-verify end-to-end:
   - `cursor-agent models` succeeds
   - `/model` shows entries in a fresh interactive session
5. If the script reports `No known picker signature matched` and dumps anchor context:
   - Cause: upstream cursor-cli bundle shape changed since this skill was last updated.
   - Recovery (do not retry the script blindly):
     1. Read the printed anchor-context block. It shows the current minified code
        around the picker call (`useModelParameters:!0,doNotUseMarkdown:!0`).
     2. Identify the as-shipped buggy form (an `n.some((...parameterDefinitions...))?n:void 0` expression).
        That string becomes the new `OLD_C_SIGNATURE`.
     3. Write the variant-preserving patched form: first filter to models with
        `parameterDefinitions`, then fall back to all non-excluded models so the
        picker is never empty. That string becomes the new `V2_C_SIGNATURE`.
     4. Edit both constants in the Python heredoc inside `scripts/fix_cursor_cli.sh`
        and re-run with `--reason empty-picker`.
   - The script header documents the bug semantics in one paragraph; read it before editing.
6. Share learning:
   - state what symptom was detected, what fix was chosen, and why this machine differed (if known)

## Assets

- `scripts/fix_cursor_cli.sh`: diagnose-first repair script with explicit symptom modes; removes quarantine from current Homebrew `cursor-cli` payload and applies dynamic bundle patch detection/replacement for the `/model` empty-list regression only when indicated.

## Output requirements

- Lead with diagnosis and confidence level.
- Include evidence for the chosen path (commands/results, not guesses).
- State whether `fix_cursor_cli.sh` changed anything (patched/already-patched/no-op).
- If interactive verification cannot be automated, ask the user to confirm `/model` after restart.

## Constraints

- Evidence-first: verify before and after each remediation step.
- Do not run repair steps preemptively on healthy machines.
- Prefer the bundled skill asset over ad-hoc manual edits.
- Treat fixes as machine-local and temporary; re-evaluate on each host/update.
